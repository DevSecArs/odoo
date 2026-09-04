
from odoo import fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    consent_id = fields.Many2one('base.consent', string='Доверенность')
