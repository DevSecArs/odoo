from odoo import models, fields, api


class uom(models.Model):
    _inherit="uom.uom"

    okei = fields.Char(string="Код ОКЕИ")

class uom_category(models.Model):
    _inherit="uom.category"

    okei = fields.Char(string="Код ОКЕИ категории")

class uom_move(models.Model):
    _inherit="account.move.line"

    uom_okei = fields.Char(string='Код ОКЕИ',related='product_uom_id.okei')
