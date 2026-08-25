from odoo.exceptions import ValidationError
from odoo.addons.hr_recruitment_pdf_offer.wizard.offer_pdf_send_wizard import _attachment_filename

from .common import OfferPdfCase


class TestOfferPdfWizard(OfferPdfCase):
    def setUp(self):
        super().setUp()
        self.template, self.document = self.create_template_with_document()
        self.applicant = self.env['hr.applicant'].create({
            'candidate_id': self.env['hr.candidate'].create({
                'partner_name': 'Иванов Иван Иванович',
                'email_from': 'ivanov@example.test',
            }).id,
            'job_id': self.env['hr.job'].create({'name': 'Engineer', 'company_id': self.env.company.id}).id,
            'company_id': self.env.company.id,
        })

    def test_defaults_can_be_edited_and_required_blocks_navigation(self):
        name_field = self.document.field_ids.filtered(lambda field: field.pdf_field_name == 'candidate_name')
        name_field.write({'default_source': 'candidate_name', 'required': True})
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        value = wizard.current_document_id.value_ids.filtered(lambda item: item.pdf_field_name == 'candidate_name')
        self.assertEqual(value.value, 'Иванов Иван Иванович')
        value.value = 'Иванов И. И.'
        self.assertTrue(wizard.preview_stale)
        with self.assertRaises(ValidationError):
            wizard.action_next()
        wizard.action_refresh_preview()
        self.assertFalse(wizard.preview_stale)
        self.assertEqual(value.value, 'Иванов И. И.')

    def test_one_document_uses_done_and_rejects_multiple_applicants(self):
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        self.assertEqual(wizard.document_count, 1)
        self.assertEqual(wizard.current_index, 0)
        self.assertEqual(wizard.current_document_id, wizard.document_ids)
        self.assertEqual(_attachment_filename(wizard.current_document_id), 'offer_filled.pdf')
