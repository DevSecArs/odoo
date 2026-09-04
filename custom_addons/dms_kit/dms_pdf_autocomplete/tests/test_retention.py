from odoo import fields

from .common import DmsPdfAutocompleteCase


class TestRetention(DmsPdfAutocompleteCase):
    def test_positive_retention_creates_and_cleans_history(self):
        wizard = self.create_wizard()
        wizard.action_prepare_mappings()
        wizard.action_prepare_values()
        wizard.write({'state': 'review', 'retention_days': 2})
        wizard.action_generate()
        self.assertTrue(wizard.batch_id)
        self.assertEqual(len(wizard.batch_id.result_ids), 1)
        attachment = wizard.batch_id.result_ids.attachment_id
        wizard.batch_id.expires_at = fields.Datetime.now()
        self.env['dms.pdf.generation.batch']._cron_cleanup_expired()
        self.assertFalse(wizard.batch_id.exists())
        self.assertFalse(attachment.exists())
