import time
from ast import literal_eval
from odoo import _, api, fields, models
from odoo.tools import date_utils,pycompat
from odoo.tools.misc import format_date
from markupsafe import Markup
from pytils import dt,numeral
from datetime import datetime, date
import re
import urllib
from odoo.exceptions import UserError

class GeneralLedgerReportWizard(models.TransientModel):
    """General ledger report wizard."""

    _name = "general.ledger.act_revise.wizard"
    _description = "General Ledger Report Wizard"
    _inherit = "act_revise.abstract_wizard"

    # date_range_id = fields.Many2one(comodel_name="date.range", string="Date range")
    date_from = fields.Date(string="Начало даты", required=True, default=lambda self: self._init_date_from())
    date_to = fields.Date(string="Конец даты", required=True, default=fields.Date.context_today)
    fy_start_date = fields.Date(compute="_compute_fy_start_date")
    target_move = fields.Selection(
        [("posted", "Все проведенные проводки"), ("all", "Все проводки")],
        string="Цель операции",
        required=True,
        default="posted",
    )
    account_ids = fields.Many2many(
        comodel_name="account.account", string="Filter accounts"
    )
    centralize = fields.Boolean(string="Activate centralization", default=True)
    hide_account_at_0 = fields.Boolean(
        string="Hide account ending balance at 0",
        help="Use this filter to hide an account or a partner "
        "with an ending balance at 0. "
        "If partners are filtered, "
        "debits and credits totals will not match the trial balance.",
    )
    receivable_accounts_only = fields.Boolean()
    payable_accounts_only = fields.Boolean()
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Партнер",
        default=lambda self: self._default_partner(),
    )
    account_journal_ids = fields.Many2many(
        comodel_name="account.journal", string="Filter journals"
    )
    cost_center_ids = fields.Many2many(
        comodel_name="account.analytic.account", string="Filter cost centers"
    )

    not_only_one_unaffected_earnings_account = fields.Boolean(readonly=True)
    foreign_currency = fields.Boolean(
        string="Show foreign currency",
        help="Display foreign currency for move lines, unless "
        "account currency is not setup through chart of accounts "
        "will display initial and final balance in that currency.",
        default=lambda self: self._default_foreign_currency(),
    )
    account_code_from = fields.Many2one(
        comodel_name="account.account",
        help="Starting account in a range",
    )
    account_code_to = fields.Many2one(
        comodel_name="account.account",
        help="Ending account in a range",
    )
    grouped_by = fields.Selection(
        selection=[("", "None"), ("partners", "Partners"), ("taxes", "Taxes")],
        default="partners",
    )
    show_cost_center = fields.Boolean(
        string="Show Analytic Account",
        default=True,
    )
    domain = fields.Char(
        string="Journal Items Domain",
        default=[],
        help="This domain will be used to select specific domain for Journal " "Items",
    )

    # def _print_report(self, report_type):
    #     self.ensure_one()
    #     data = self._prepare_report_general_ledger()
    #     report = self.env["ir.actions.report"].search(
    #         [("report_name", "=", "act_revise.general_ledger"), ("report_type", "=", report_type)], limit=1, )
    #     if self.partner_ids[0].parent_id:
    #         partner = int(self.partner_ids[0].parent_id.id)
    #     else:
    #         partner = int(self.partner_ids[0].id)
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': '/my/act_revise_contact/%s?date_to=%s&date_from=%s&target_move=%s&company=%s&partner=%s' % (
    #             urllib.parse.quote(self.get_report_filename()), self.date_to, self.date_from, self.target_move,
    #             self.company_id.id, partner),
    #         'target': 'new',
    #     }

    def _get_account_move_lines_domain(self):
        domain = literal_eval(self.domain) if self.domain else []
        return domain

    @api.onchange("account_code_from", "account_code_to")
    def on_change_account_range(self):
        if (
            self.account_code_from
            and self.account_code_from.code.isdigit()
            and self.account_code_to
            and self.account_code_to.code.isdigit()
        ):
            start_range = self.account_code_from.code
            end_range = self.account_code_to.code
            self.account_ids = self.env["account.account"].search(
                [("code", ">=", start_range), ("code", "<=", end_range)]
            )
            if self.company_id:
                self.account_ids = self.account_ids.filtered(
                    lambda a: self.company_id in a.company_ids
                )

    def _init_date_from(self):
        """set start date to begin of current year if fiscal year running"""
        today = fields.Date.context_today(self)
        company = self.company_id or self.env.company
        last_fsc_month = company.fiscalyear_last_month
        last_fsc_day = company.fiscalyear_last_day

        if (
            today.month < int(last_fsc_month)
            or today.month == int(last_fsc_month)
            and today.day <= last_fsc_day
        ):
            return time.strftime("%Y-01-01")
        else:
            return False

    def _default_foreign_currency(self):
        return self.env.user.has_group("base.group_multi_currency")

    @api.depends("date_from")
    def _compute_fy_start_date(self):
        for wiz in self:
            if wiz.date_from:
                date_from, date_to = date_utils.get_fiscal_year(
                    wiz.date_from,
                    day=self.company_id.fiscalyear_last_day,
                    month=int(self.company_id.fiscalyear_last_month),
                )
                wiz.fy_start_date = date_from
            else:
                wiz.fy_start_date = False

    @api.onchange("company_id")
    def onchange_company_id(self):
        """Handle company change."""
        if self.company_id:
            count = self.env["account.account"].search_count(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_ids", "in", [self.company_id.id]),
                ]
            )
            self.not_only_one_unaffected_earnings_account = count != 1
        else:
            self.not_only_one_unaffected_earnings_account = False
        # if (
        #     self.company_id
        #     and self.date_range_id.company_id
        #     and self.date_range_id.company_id != self.company_id
        # ):
        #     self.date_range_id = False
        if self.company_id and self.account_journal_ids:
            self.account_journal_ids = self.account_journal_ids.filtered(
                lambda p: p.company_id == self.company_id or not p.company_id
            )
        if self.company_id and self.partner_id:
            if self.partner_id.company_id and self.partner_id.company_id != self.company_id:
                self.partner_id = False
        if self.company_id and self.account_ids:
            if self.receivable_accounts_only or self.payable_accounts_only:
                self.onchange_type_accounts_only()
            else:
                self.account_ids = self.account_ids.filtered(
                    lambda a: self.company_id in a.company_ids
                )
        if self.company_id and self.cost_center_ids:
            self.cost_center_ids = self.cost_center_ids.filtered(
                lambda c: c.company_id == self.company_id
            )
        res = {
            "domain": {
                "account_ids": [],
                "partner_id": [],
                "account_journal_ids": [],
                "cost_center_ids": [],
                # "date_range_id": [],
            }
        }
        if not self.company_id:
            return res
        else:
            res["domain"]["account_ids"] += [("company_ids", "in", [self.company_id.id])]
            res["domain"]["account_journal_ids"] += [
                ("company_id", "=", self.company_id.id)
            ]
            res["domain"]["partner_id"] += self._get_partner_ids_domain()
            res["domain"]["cost_center_ids"] += [
                ("company_id", "=", self.company_id.id)
            ]
            # res["domain"]["date_range_id"] += [
            #     "|",
            #     ("company_id", "=", self.company_id.id),
            #     ("company_id", "=", False),
            # ]
        return res

    # @api.onchange("date_range_id")
    # def onchange_date_range_id(self):
    #     """Handle date range change."""
    #     if self.date_range_id:
    #         self.date_from = self.date_range_id.date_start
    #         self.date_to = self.date_range_id.date_end

    # @api.constrains("company_id", "date_range_id")
    # def _check_company_id_date_range_id(self):
    #     for rec in self.sudo():
    #         if (
    #             rec.company_id
    #             and rec.date_range_id.company_id
    #             and rec.company_id != rec.date_range_id.company_id
    #         ):
    #             raise ValidationError(
    #                 _(
    #                     "The Company in the General Ledger Report Wizard and in "
    #                     "Date Range must be the same."
    #                 )
    #             )

    @api.onchange("receivable_accounts_only", "payable_accounts_only")
    def onchange_type_accounts_only(self):
        """Handle receivable/payable accounts only change."""
        if self.receivable_accounts_only or self.payable_accounts_only:
            domain = []  # Start with empty domain
            
            # Add company filter ONLY if company is selected
            if self.company_id:
                domain.append(("company_ids", "in", [self.company_id.id]))
            
            # Add account type conditions
            if self.receivable_accounts_only and self.payable_accounts_only:
                domain.append(
                    ("account_type", "in", ("asset_receivable", "liability_payable"))
                )
            elif self.receivable_accounts_only:
                domain.append(("account_type", "=", "asset_receivable"))
            elif self.payable_accounts_only:
                domain.append(("account_type", "=", "liability_payable"))
                
            self.account_ids = self.env["account.account"].search(domain)
        else:
            self.account_ids = None

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """Handle partner change."""
        if self.partner_id:
            self.receivable_accounts_only = self.payable_accounts_only = True
        else:
            self.receivable_accounts_only = self.payable_accounts_only = False

    @api.depends("company_id")
    def _compute_unaffected_earnings_account(self):
        for record in self:
            if record.company_id:
                record.unaffected_earnings_account = self.env["account.account"].search(
                    [
                        ("account_type", "=", "equity_unaffected"),
                        ("company_ids", "in", [record.company_id.id]),
                    ],
                    limit=1
                )
            else:
                record.unaffected_earnings_account = False

    unaffected_earnings_account = fields.Many2one(
        comodel_name="account.account",
        compute="_compute_unaffected_earnings_account",
        store=True,
    )

    # def _print_report(self, report_type):
    #     self.ensure_one()
    #     data = self._prepare_report_general_ledger()
    #     report_name = "act_revise.general_ledger"
    #     return (
    #         self.env["ir.actions.report"]
    #         .search(
    #             [("report_name", "=", report_name), ("report_type", "=", report_type)],
    #             limit=1,
    #         )
    #         .report_action(self, data=data)
    #     )
    def _print_report(self, report_type):
        self.ensure_one()
        
        # Проверяем, что выбран один и только один партнер
        if not self.partner_id:
            raise UserError('Необходимо выбрать партнера для формирования акта сверки.')
        
        # Определяем ID партнера (учитываем parent_id)
        partner_record = self.partner_id
        if partner_record.parent_id:
            partner_id = partner_record.parent_id.id
            partner_name = partner_record.parent_id.name
        else:
            partner_id = partner_record.id
            partner_name = partner_record.name
            
        # Проверяем наличие проводок для данного партнера
        non_trade_filtered_moves = self.env['account.move.line'].sudo().search([
            ('partner_id', '=', partner_id),
            ('account_id.account_type', 'in', ('liability_payable', 'asset_receivable')),
            ('account_id.non_trade', '=', False),
            ('date', '<=', self.date_to),
            ('date', '>=', self.date_from),
            ('company_id', '=', self.company_id.id)
        ])
        
        if self.target_move == 'posted':
            account_data = non_trade_filtered_moves.filtered(lambda p: p.parent_state == 'posted')
        else:
            account_data = non_trade_filtered_moves
            
        # Если нет проводок, показываем ошибку
        if not account_data:
            raise UserError(f'У партнера "{partner_name}" нет проводок для формирования акта сверки за период с {self.date_from} по {self.date_to}.')
        
        # Если есть проводки, формируем акт сверки
        return self.with_context(override_partner_id=partner_id)._generate_report_for_selected_partner(report_type)

    def _prepare_report_general_ledger(self):
        self.ensure_one()
        return {
            "wizard_id": self.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "only_posted_moves": self.target_move == "posted",
            "hide_account_at_0": self.hide_account_at_0,
            "foreign_currency": self.foreign_currency,
            "company_id": self.company_id.id,
            "company_name": self.company_id.name,
            "account_ids": self.account_ids.ids,
            "partner_ids": [self.partner_id.id] if self.partner_id else [],
            "grouped_by": self.grouped_by,
            "cost_center_ids": self.cost_center_ids.ids,
            "show_cost_center": self.show_cost_center,
            "journal_ids": self.account_journal_ids.ids,
            "centralize": self.centralize,
            "fy_start_date": self.fy_start_date,
            "unaffected_earnings_account": self.unaffected_earnings_account.id,
            "account_financial_report_lang": self.env.lang,
            "domain": self._get_account_move_lines_domain(),
        }

    def _export(self, report_type):
        """Default export is PDF."""
        return self._print_report(report_type)

    def _generate_report_for_selected_partner(self, report_type=None):
        """Generate report for selected partner from selection wizard."""
        self.ensure_one()
        
        # Получаем ID партнера из контекста или из wizard выбора
        partner_id = self.env.context.get('override_partner_id')
        if not partner_id:
            raise UserError('Не указан партнер для формирования акта сверки.')
        
        # Подготавливаем данные для отчета
        data = self._prepare_report_general_ledger()
        
        # Ищем отчет
        report = self.env["ir.actions.report"].search(
            [("report_name", "=", "l10n_ru_act_rev.general_ledger"), ("report_type", "=", report_type or "qweb-pdf")], limit=1)
        
        # Получаем имя партнера для формирования имени файла
        partner_record = self.env['res.partner'].browse(partner_id)
        partner_name = partner_record.parent_id.name if partner_record.parent_id else partner_record.name
        
        # Формируем имя файла
        today = fields.Date.context_today(self)
        d1 = today.strftime("%d-%m-%Y")
        filename = f'Акт сверки {partner_name} {d1}'
        
        # Генерируем URL для отчета
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/act_revise_contact/%s?date_to=%s&date_from=%s&target_move=%s&company=%s&partner=%s' % (
                urllib.parse.quote(filename), self.date_to, self.date_from, self.target_move,
                self.company_id.id, partner_id),
            'target': 'new',
        }

    def _get_atr_from_dict(self, obj_id, data, key):
        try:
            return data[obj_id][key]
        except KeyError:
            return data[str(obj_id)][key]

    def numer(self, name):
        if name:
            numeration = re.findall(r'\d+$', name)
            if numeration: return numeration[0]
        return name

    def get_data_format(self, date):
        if date and date != 'False':
            return dt.ru_strftime(u'%d.%m.%Y г.', date=datetime.strptime(str(date), "%Y-%m-%d"), inflected=True)
        return ''

    def initials(self, fio):
        if fio:
            return (fio.split()[0] + ' ' + ''.join([fio[0:1] + '.' for fio in fio.split()[1:]])).strip()
        return ''

    def rubles(self, sum):
        "Transform sum number in rubles to text"
        text_rubles = numeral.rubles(int(sum))
        copeck = round((sum - int(sum)) * 100)
        text_copeck = numeral.choose_plural(int(copeck), (u"копейка", u"копейки", u"копеек"))
        return ("%s %02d %s") % (text_rubles, copeck, text_copeck)

    def img(self, img, type='png', width=0, height=0):
        if width:
            width = "width='%spx'" % (width)
        else:
            width = " "
        if height:
            height = "height='%spx'" % (height)
        else:
            height = " "
        html_content = "<img %s %s src='data:image/%s;base64,%s' />" % (
            width,
            height,
            type,
            str(pycompat.to_text(img)))
        return Markup(html_content)

    def get_contract(self):
        if not self.partner_id:
            return None
        partner = int(self.partner_id.id)
        contract = self.env['partner.contract.customer'].search(
            [('partner_id', '=', partner), ('state', '=', 'signed')], limit=1)
        if contract:
            return contract

    def get_function_partner(self, partner):
        director = self.env['res.partner'].search([('parent_id', '=', partner), ('type', '=', 'director')], limit=1)
        if director:
            if director.function:
                return director.function or 'отсутствует'

    def get_name_partner(self, partner):
        director = self.env['res.partner'].search([('parent_id', '=', partner), ('type', '=', 'director')], limit=1)
        if director:
            return director.name or 'отсутствует'

    def get_report_filename(self):
        today = date.today()
        d1 = today.strftime("%d-%m-%Y")
        
        # Проверяем, что есть партнер
        if not self.partner_id:
            return f'Акт сверки {d1}'
        
        # Для одного партнера - стандартное имя
        partner_record = self.partner_id
        if partner_record.parent_id:
            p = ''.join(c for c in partner_record.parent_id.name if c.isalnum() or c in (' ', '-', '_')).strip()
        else:
            p = ''.join(c for c in partner_record.name if c.isalnum() or c in (' ', '-', '_')).strip()
        return f'Акт сверки {p} {d1}'

    def sorted_lines(self, list):
        list = sorted(list, key=lambda k: k.get('date'), reverse=False)
        return list

    def _default_partner(self):
        context = self.env.context
        if context.get("active_ids") and context.get("active_model") == "res.partner":
            # For single partner selection from partner form view
            partner = self.env["res.partner"].browse(context["active_ids"][0])
            if partner.parent_id:
                return partner.parent_id.id
            else:
                return partner.id
        return False
