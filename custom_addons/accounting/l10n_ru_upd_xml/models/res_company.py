from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    edi = fields.Char(string='ID EDI', readonly=False)