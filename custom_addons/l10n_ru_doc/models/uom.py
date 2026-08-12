from odoo import fields, models

class UomInherit(models.Model):
    _inherit = 'uom.uom'
    kod = fields.Char('Код единицы измерения')

class UomCategoryInherit(models.Model):
    _inherit = 'uom.category'
    kod = fields.Char('Код категории единицы измерения')
