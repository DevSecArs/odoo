import base64
import io
import zipfile

from odoo import fields
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.pdf_form_core.services import inspect_pdf

from ..wizard.pdf_autocomplete_wizard import safe_pdf_filename

from .common import DmsPdfAutocompleteCase


class TestPdfAutocompleteWizard(DmsPdfAutocompleteCase):
    def _prepare(self, partners=None):
        wizard = self.create_wizard(partners=partners)
        wizard.action_prepare_mappings()
        name = wizard.mapping_ids.filtered(lambda item: item.pdf_field_name == 'name')
        name.write({'fill_mode': 'odoo_field', 'source_field_path': 'name'})
        wizard.action_prepare_values()
        return wizard

    def test_requires_recipient(self):
        wizard = self.create_wizard()
        wizard.partner_ids = [(5, 0, 0)]
        with self.assertRaises(ValidationError):
            wizard.action_prepare_mappings()

    def test_saved_mapping_is_loaded(self):
        wizard = self._prepare()
        second = self.create_wizard(file=wizard.source_file_id)
        second.action_prepare_mappings()
        mapping = second.mapping_ids.filtered(lambda item: item.pdf_field_name == 'name')
        self.assertEqual(mapping.source_field_path, 'name')

    def test_values_are_personalized(self):
        wizard = self._prepare(self.partner_a | self.partner_b)
        values = {
            recipient.display_name_snapshot: recipient.value_ids.filtered(
                lambda item: item.pdf_field_name == 'name'
            ).value
            for recipient in wizard.recipient_ids
        }
        self.assertEqual(values['Иван Иванов'], 'Иван Иванов')
        self.assertEqual(values['Пётр Петров'], 'Пётр Петров')

    def test_manual_values_are_per_recipient(self):
        wizard = self._prepare(self.partner_a | self.partner_b)
        recipients = wizard.recipient_ids.sorted('id')
        recipients[0].manual_value_ids.value = 'A'
        recipients[1].manual_value_ids.value = 'B'
        self.assertEqual(recipients[0].manual_value_ids.value, 'A')
        self.assertEqual(recipients[1].manual_value_ids.value, 'B')

    def test_preview_and_final_generation(self):
        wizard = self._prepare()
        wizard.current_recipient_id.manual_value_ids.value = 'Preview'
        wizard.action_preview_current()
        self.assertTrue(wizard.current_recipient_id.preview_pdf)
        wizard.write({'state': 'review'})
        wizard.action_generate()
        recipient = wizard.recipient_ids
        self.assertTrue(recipient.output_pdf)
        self.assertEqual(recipient.output_filename.count('/'), 0)
        self.assertEqual(
            {item['name'] for item in inspect_pdf(base64.b64decode(recipient.output_pdf))},
            {'name', 'note'},
        )

    def test_retention_zero_creates_no_history(self):
        wizard = self._prepare()
        wizard.write({'state': 'review', 'retention_days': 0})
        wizard.action_generate()
        self.assertFalse(wizard.batch_id)

    def test_zip_contains_one_safe_pdf_per_recipient(self):
        wizard = self._prepare(self.partner_a | self.partner_b)
        wizard.write({'state': 'review'})
        wizard.action_generate()
        archive = zipfile.ZipFile(io.BytesIO(wizard._build_zip()))
        self.assertEqual(len(archive.namelist()), 2)
        self.assertTrue(all(name.endswith('.pdf') for name in archive.namelist()))
        self.assertTrue(all('/' not in name and '\\' not in name for name in archive.namelist()))

    def test_long_output_filenames_keep_unique_record_id(self):
        first = safe_pdf_filename('x' * 200 + '.pdf', 'recipient' * 30, 101)
        second = safe_pdf_filename('x' * 200 + '.pdf', 'recipient' * 30, 102)
        self.assertNotEqual(first.casefold(), second.casefold())
        self.assertTrue(first.endswith(' - 101.pdf'))

    def test_download_action_creates_expiring_token(self):
        wizard = self._prepare()
        wizard.write({'state': 'review'})
        action = wizard.action_download()
        self.assertIn(wizard.download_token, action['url'])
        self.assertFalse(wizard.download_token_used)
        self.assertTrue(wizard.download_token_expires_at)

    def test_download_token_is_single_use(self):
        wizard = self._prepare()
        wizard.write({'state': 'review'})
        wizard.action_download()
        self.assertTrue(wizard._consume_download_token(wizard.download_token))
        with self.assertRaises(AccessError):
            wizard._consume_download_token(wizard.download_token)

    def test_expired_download_token_is_rejected(self):
        wizard = self._prepare()
        wizard.write({'state': 'review'})
        wizard.action_download()
        wizard.download_token_expires_at = fields.Datetime.subtract(
            fields.Datetime.now(), minutes=1,
        )
        with self.assertRaises(AccessError):
            wizard._consume_download_token(wizard.download_token)
