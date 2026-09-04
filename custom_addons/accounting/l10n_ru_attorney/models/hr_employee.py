
from odoo import fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    inn = fields.Char(string="ИНН")
    pass_kem = fields.Char(string="Кем выдан паспорт")
    pass_date = fields.Date(string='Дата выдачи паспорта')
