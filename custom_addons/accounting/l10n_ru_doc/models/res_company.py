from odoo import fields, models

class Company(models.Model):
    _inherit = 'res.company'

    inn = fields.Char(related='partner_id.inn', readonly=False)
    kpp = fields.Char(related='partner_id.kpp', readonly=False)
    okpo = fields.Char(related='partner_id.okpo', readonly=False)
    chief_id = fields.Many2one('res.users', 'Руководитель')
    accountant_id = fields.Many2one('res.users', 'Главный бухгалтер')
    print_facsimile = fields.Boolean(string='Печать факсимиле',
                    help="Отметьте для добавления факсимиле ответственных лиц в документы.")
    print_stamp = fields.Boolean(string='Печать штампа',
                                 help="Отметьте для добавления печати компании в документы.")
    stamp = fields.Binary("Печать")
    print_anywhere = fields.Boolean(string='Печать везде',
                    help="Снимите отметку, если хотите добавлять факсимиле и печать только в email.",
                    default=True)
