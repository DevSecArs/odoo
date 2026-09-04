
from odoo import api, fields, models, _
from datetime import datetime, timedelta


class BaseConsent(models.Model):
    _name = 'base.consent'
    _inherit = ['mail.thread', 'utm.mixin']
    _description = 'Consent'
    _order = 'date_from desc'

    name = fields.Char(string='Номер')
    date_from = fields.Date(string='Дата выдачи', default=lambda self: fields.Datetime.now())
    date_to = fields.Date(string='Действительна по', default=lambda self: datetime.today() + timedelta(days=180))
    partner_id = fields.Many2one('res.partner', string='Контрагент', required=True)
    employee_id = fields.Many2one('hr.employee', string='Сотрудник', required=True)
    purchaseorder_id = fields.Many2one('purchase.order', 'Заказ на закупку', domain="[('partner_id','=',partner_id)]",
                                       required=True)
    company_id = fields.Many2one('res.company', string='Компания',
                                 default=lambda self: self.env['res.company']._company_default_get('base.consent'),
                                 required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            name = self.env['ir.sequence'].next_by_code('base.consent')
            if name:
                if 'name' in val:
                    if val['name'] == False:
                        val.update({
                            'name': name,
                        })

        result = super().create(vals_list)
        return result

    @api.onchange('purchaseorder_id')
    def set_partner(self):
        if self.purchaseorder_id:
            self.partner_id = self.purchaseorder_id.partner_id

    @api.constrains('purchaseorder_id')
    def fill_order(self):
        p_orders = self.env['purchase.order'].sudo().browse(self.purchaseorder_id.id)
        for order in p_orders:
            order.consent_id = self.id
