from odoo import models

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env['report'].get_action(self, 'l10n_ru_doc.report_order')

