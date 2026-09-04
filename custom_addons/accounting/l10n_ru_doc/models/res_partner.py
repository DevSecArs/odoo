from odoo import fields, models
class ResPartner(models.Model):
    _inherit = 'res.partner'

    inn = fields.Char('ИНН', related='vat')
    kpp = fields.Char('КПП', size=9)
    okpo = fields.Char('ОКПО', size=14)
    ogrn = fields.Char('ОГРН')
    type = fields.Selection(selection_add=[('director', 'Директор'), ('accountant', 'Бухгалтер')])
    facsimile = fields.Binary("Подпись")
    stamp = fields.Binary("Печать")
