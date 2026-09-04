from odoo import api, fields, models, exceptions, tools
import pymorphy2
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .crutch_fields_header import IP_CONTACT_HEADER, ENTITY_CONTRACT_HEADER, INDIVIDUAL_CONTRACT_HEADER


class PartnerContractCustomer(models.Model):
    _name = 'partner.contract.customer'
    _description = 'Customer Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mail.render.mixin']

    def get_dateend(self):
        if self.date_start:
            six_months = fields.Datetime.from_string(self.date_start) + relativedelta(months=+11)
        else:
            six_months = datetime.today() + relativedelta(months=+11)
        return fields.Datetime.to_string(six_months)

    name = fields.Char(string='Номер')
    date_start = fields.Date(string='Дата договора', required=True, default=fields.Datetime.now())
    partner_id = fields.Many2one('res.partner', string='Контрагент', required=True)
    sec_partner_id = fields.Many2one('res.partner', string='Контрагент как в заказе')
    company_id = fields.Many2one('res.company', string='Компания', required=True)
    name_print = fields.Char(string='Имя для печати', compute='_get_name_print')
    name_print1 = fields.Char(string='Имя для печати, И.П.', compute='_get_name_printip')
    date_end = fields.Date(string='Дата окончания', required=True, default=get_dateend)
    name_dirprint = fields.Char(string='Имя нашего директора для печати')
    name_dirprint1 = fields.Char(string='Имя нашего директора для печати И.П.', compute='_get_name_print1ip')
    lines = fields.One2many('contract.line', 'contract_id', string='Договорные цены')
    type = fields.Selection(
        [('customer', 'С покупателем'),
         ('supplier', 'С поставщиком'),
         ('other', 'Прочие расчеты'),

         ],
        string='Тип договора', default='customer', required=True)
    saleorder_id = fields.Many2one('sale.order', string='Заказ/Сделка')
    stamp = fields.Boolean(string='Печать и подпись')
    signed = fields.Boolean(string='Договор подписан')
    state = fields.Selection(
        [('draft', 'Черновик'),
         ('progress', 'На согласовании'),
         ('signed', 'Подписан, действует'),
         ('closed', 'Истёк'),
         ],
        string='Статус', default='draft', group_expand='_expand_states', index=True
    )
    is_template = fields.Boolean('Это шаблон')
    copy_from = fields.Many2one('partner.contract.customer', string='Копировать из этого шаблона')
    profile_id = fields.Many2one('contract.profile', string='Вид договора', required=True)
    credit_limit = fields.Float(string='Лимит кредита')
    guid_1s = fields.Char('Код договора из 1С')
    buh_code = fields.Char('Код договора из бухгалтерии')
    payment_term_id = fields.Many2one('account.payment.term', string='Условие оплаты')
    manager_id = fields.Many2one('res.users', string='Менеджер по продажам')
    accountant_id = fields.Many2one('res.users', string='Бухгалтер по взаиморасчетам')
    time_to_delivery_from = fields.Datetime('Время доставки от')
    time_to_delivery_to = fields.Datetime('Время доставки до')
    day_of_delivery = fields.Float('Дни доставки')
    day_of_otgruzki = fields.Float('Дни отгрузки')

    # Removed channel_id field due to missing 'saleorder.channel' model in Odoo 18
    # channel_id = fields.Many2one('saleorder.channel', string='Канал продаж')
    team_id = fields.Many2one('crm.team', string='Команда продаж')
    order_days_ids = fields.Many2many(comodel_name='contract.day', relation='orderdays', string='Дни доставки',
                                      column1='contract_id', column2='day_id')
    shipment_days_ids = fields.Many2many(comodel_name='contract.day', relation='shipmentdays', string='Дни отгрузки',
                                         column1='contract_id',
                                         column2='day_id')
    # Доработка хедера договора
    partner_type = fields.Selection(string='Тип контрагента', selection=[
        ('person', 'Физ. лицо'),
        ('company_ip', 'ИП'),
        ('company', 'Юр. лицо')
    ], required=True, default='company')
    contract_header = fields.Html('Шапка договора')

    @api.onchange('partner_type')
    def generate_contract_header(self):
        self.ensure_one()
        self.render_model = 'partner.contract.customer'
        if self.partner_type == 'company_ip':
            self.contract_header = IP_CONTACT_HEADER
        elif self.partner_type == 'person':
            self.contract_header = INDIVIDUAL_CONTRACT_HEADER
        else:
            self.contract_header = ENTITY_CONTRACT_HEADER
        # # Рендер Jinja выражение типа {{object.field}}
        result = self._render_template(self.contract_header, self.render_model, res_ids=[self.id])
        result = tools.html_sanitize(result[self.id])
        self.contract_header = result

    @api.onchange('sec_partner_id')
    def set_pid(self):
        self.partner_id = self.sec_partner_id.parent_id if self.sec_partner_id.parent_id else self.sec_partner_id

    @api.model
    def _expand_states(self, states, domain, order=None):
        """Ensure all states are visible in kanban view grouping"""
        # Get all state options from field definition
        all_states = [key for key, val in self._fields['state'].selection]
        return all_states

    def copy_it(self):
        if self.copy_from:
            for line in self.copy_from.lines:
                line.copy({'contract_id': self.id})

    def _get_name_print(self):
        morph = pymorphy2.MorphAnalyzer()
        self.name_print = False
        director = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id), ('type', '=', 'director')],
                                                  limit=1)
        if director:
            if len(director.name.split(' ')) == 3:
                lastname_old, firstname_old, middlename_old = director.name.split(' ')

                if lastname_old:
                    lastname_n = morph.parse(lastname_old)[0]
                    if lastname_n.inflect({'gent'}):
                        lastname_n = lastname_n.inflect({'gent'}).word
                    else:
                        lastname_n = lastname_old
                else:
                    lastname_n = ''

                if firstname_old:
                    firstname_n = morph.parse(firstname_old)[0]
                    firstname_n = firstname_n.inflect({'gent'}).word
                else:
                    firstname_n = ''

                if middlename_old:
                    middlename_n = morph.parse(middlename_old)[0]
                    middlename_n = middlename_n.inflect({'gent'}).word
                else:
                    middlename_n = ''

                name_print = lastname_n + ' ' + firstname_n + ' ' + middlename_n

                self.name_print = name_print.title()

    def _get_name_print1(self):
        morph = pymorphy2.MorphAnalyzer()
        director = self.company_id.chief_id.partner_id if self.company_id.chief_id else False
        # raise exceptions.UserError(str(director))
        self.name_dirprint = False
        if director:
            if len(director.name.split(' ')) == 3:
                lastname_old, firstname_old, middlename_old = director.name.split(' ')

                if lastname_old:
                    lastname_n = morph.parse(lastname_old)[0]
                    lastname_n = lastname_n.inflect({'gent'}).word
                else:
                    lastname_n = ''

                if firstname_old:
                    firstname_n = morph.parse(firstname_old)[0]
                    firstname_n = firstname_n.inflect({'gent'}).word
                else:
                    firstname_n = ''

                if middlename_old:
                    middlename_n = morph.parse(middlename_old)[0]
                    middlename_n = middlename_n.inflect({'gent'}).word
                else:
                    middlename_n = ''

                name_print = lastname_n + ' ' + firstname_n + ' ' + middlename_n

                self.name_dirprint = name_print.title()

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PartnerContractCustomer, self).create(vals_list)

        for record, values in zip(res, vals_list):
            if values.get('is_template'):
                continue

            if values.get('type') == 'customer':
                sequence_code = 'partner.contract.customer.sequence'
            elif values.get('type') == 'supplier':
                sequence_code = 'partner.contract.supplier.sequence'
            else:
                continue

            name = self.env['ir.sequence'].next_by_code(sequence_code)
            record.update({
                'name': name,
            })
            
        return res









    # @api.model
    def write(self, values):

        if 'state' in values:
            if self.state != values['state']:
                msg = 'Статус: ' + dict(self._fields['state'].selection).get(self.state) + ' -> ' + dict(
                    self._fields['state'].selection).get(values['state'])
                self.message_post(body=msg)
        res = super(PartnerContractCustomer, self).write(values)
        return res

    def _get_name_print1ip(self):
        self.name_dirprint1 = self.company_id.chief_id.partner_id.name if self.company_id.chief_id else False

    def get_function_partner1(self, partner_id):
        """Get the function/position of the director for the given partner"""
        partner = self.env['res.partner'].browse(partner_id)
        director = self.env['res.partner'].search([
            ('parent_id', '=', partner.id), 
            ('type', '=', 'director')
        ], limit=1)
        return director.function if director else ''

    def _get_name_printip(self):
        self.name_print1 = False
        director = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id), ('type', '=', 'director')],
                                                  limit=1)
        if director:
            self.name_print1 = director.name

    def print_supp(self):
        # self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env.ref('mta_base.action_mtacontractsupp_report').report_action(self)

    def print_contract_cust(self):
        if self.saleorder_id:
            return self.saleorder_id.print_contract()
        else:
            raise exceptions.UserError(
                'Вы не можете напечатать договор с Клиентом, потому что нет связи с Заказом. Нужно зайти в Заказ и привязать этот договор.')

    def contract_action_confirm(self):
        if self.state == 'draft':
            self.state = 'progress'
        elif self.state == 'progress':
            self.state = 'signed'

    def contract_in_draft(self):
        self.state = 'draft'

    @api.onchange('name')
    def set_comp_and_partn(self):
        context = self._context
        order_id = context.get('sale_order_id')
        if order_id:
            sale_order = self.env['sale.order'].browse(order_id)

            self.company_id = sale_order.company_id
            self.partner_id = sale_order.partner_id

    @api.onchange('profile_id')
    def set_payment(self):
        if self.profile_id.payment_term_id:
            self.payment_term_id = self.profile_id.payment_term_id

    # @api.constrains('name')
    def check_name(self):
        obj = self.search([('name', '=', self.name), ('id', '!=', self.id), ('state', '!=', 'closed')])
        if obj:
            raise exceptions.ValidationError('Договор с таким номером уже существует')

    """
    @api.constrains('profile_id')
    def check_profile_id(self):
        contracts = self.search([('partner_id', '=', self.partner_id.id), ('id', '!=', self.id)])
        if contracts:
            profiles_in_contracts = contracts.profile_id
            #  raise exceptions.ValidationError(profiles_in_contracts.ids)
            if profiles_in_contracts:
                ads = self.env['contract.allowed.profiles'].search(
                    [('allowed_profiles', 'in', profiles_in_contracts.ids)])
                if ads:
                    raise exceptions.ValidationError((self.profile_id.name, ads.name))
        #  raise exceptions.ValidationError(contracts)
    """


class Partner(models.Model):
    _inherit = 'res.partner'

    contract_count = fields.Integer(string='Договоры', compute='get_count_contract')
    pol = fields.Selection(string="Пол", selection=[('m', 'Муж.'), ('j', 'Жен'), ], required=False)
    type = fields.Selection(selection_add=[('director', 'Директор')])

    def get_count_contract(self):
        contract = self.env['partner.contract.customer']
        self.contract_count = contract.search_count([('partner_id', '=', self.id)])

    def action_view_contract(self):
        action = self.env.ref('l10n_ru_contract.contract_customer_action').read()[0]

        action['domain'] = [('partner_id', '=', self.id)]

        return action


class ContractLine(models.Model):
    _name = 'contract.line'
    _description = 'Contract Line'
    contract_id = fields.Many2one('partner.contract.customer', string='Order Reference', required=True,
                                  ondelete='cascade', index=True, copy=False)
    _order = "sequence desc"
    price_unit = fields.Float('Цена', default=0.0)
    product_uom = fields.Many2one('uom.uom', string='Единица измерения')
    product_id = fields.Many2one('product.product', string='Услуга', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict')
    sequence = fields.Integer('Порядок')
    name = fields.Char('Номер пункта')
    punct = fields.Html('Текст пункта')

    @api.onchange('product_id')
    def set_name(self):
        if self.product_id:
            self.name = self.product_id.name


class AllowedProfiles(models.Model):
    _name = 'contract.allowed.profiles'
    _description = 'Allowed Contract Profiles'
    name = fields.Char(string='Одновременно включены следующие виды договоров:')
    allowed_profiles = fields.Many2many('contract.profile', string='Виды договоров', required=True)

    @api.onchange('allowed_profiles')
    def set_name(self):
        self.name = ''
        for profile in self.allowed_profiles:
            self.name += profile.name + ' + '
        if self.name:
            if self.name[-2] == '+':
                self.name = self.name[:-2]


class ContractProfile(models.Model):
    _name = 'contract.profile'
    _description = 'Contract Profile'
    name = fields.Char(string='Вид договора', required=True)
    payable_account_id = fields.Many2one('account.account', string='Счет кредиторской задолженности', required=True)
    receivable_account_id = fields.Many2one('account.account', string='Счет дебиторской задолженности', required=True)
    max_receivable_id = fields.Float(string='Максимальная деб. задолженность', required=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Условие оплаты', required=True)
    journal_id = fields.Many2one('account.journal', string='Журнал', required=True)


class ContractDay(models.Model):
    _name = 'contract.day'
    _description = 'Contract Day'
    name = fields.Char('День')
