from odoo.exceptions import ValidationError
from odoo.addons.hr_recruitment_pdf_renderer.wizard.offer_pdf_send_wizard import _attachment_filename

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
        self.env['mail.template.offer.pdf.document'].create({
            'name': 'Second document.pdf',
            'template_id': self.template.id,
            'pdf_filename': 'second_document.pdf',
            'pdf_file': self.document.pdf_file,
        })
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        value = wizard.current_document_id.value_ids.filtered(lambda item: item.pdf_field_name == 'candidate_name')
        self.assertEqual(value.value, 'Иванов Иван Иванович')
        value.value = 'Иванов И. И.'
        self.assertTrue(wizard.preview_stale)
        wizard.action_next()
        self.assertEqual(wizard.current_index, 1)
        wizard.action_previous()
        self.assertEqual(value.value, 'Иванов И. И.')
        wizard.action_refresh_preview()
        self.assertFalse(wizard.preview_stale)
        self.assertEqual(value.value, 'Иванов И. И.')

        value.value = 'Иванов Иван И.'
        action = wizard.action_save()
        self.assertEqual(action['res_id'], wizard.id)
        self.assertEqual(value.value, 'Иванов Иван И.')

    def test_static_default_is_copied_to_the_wizard(self):
        address_field = self.document.field_ids.filtered(
            lambda field: field.pdf_field_name == 'candidate_address'
        )
        address_field.write({
            'default_source': 'static',
            'default_text': 'г. Москва, ул. Пример, д. 1',
        })
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        value = wizard.current_document_id.value_ids.filtered(
            lambda item: item.pdf_field_name == 'candidate_address'
        )
        self.assertEqual(value.value, 'г. Москва, ул. Пример, д. 1')

    def test_wizard_uses_pdf_fields_when_a_legacy_mapping_is_incomplete(self):
        """A missing configuration row must not prevent a PDF from being filled."""
        self.document.field_ids.filtered(
            lambda field: field.pdf_field_name == 'candidate_address'
        ).unlink()

        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })

        self.assertEqual(
            wizard.current_document_id.value_ids.mapped('pdf_field_name'),
            ['candidate_name', 'candidate_address'],
        )
        wizard.action_refresh_preview()
        self.assertFalse(wizard.preview_stale)

    def test_candidate_address_never_uses_partner_email_as_an_address(self):
        partner = self.env['res.partner'].create({
            'name': 'candidate@example.test',
            'email': 'candidate@example.test',
        })
        self.applicant.candidate_id.partner_id = partner
        address_field = self.document.field_ids.filtered(
            lambda field: field.pdf_field_name == 'candidate_address'
        )
        address_field.default_source = 'candidate_address'
        self.assertEqual(address_field._get_default_value(self.applicant), '')

    def test_one_document_uses_done_and_rejects_multiple_applicants(self):
        self.document.name = 'Employment agreement.pdf'
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        self.assertEqual(wizard.document_count, 1)
        self.assertEqual(wizard.current_index, 0)
        self.assertEqual(wizard.current_document_id, wizard.document_ids)
        self.assertEqual(_attachment_filename(wizard.current_document_id), 'Employment agreement.pdf')

    def test_template_can_be_removed_while_a_wizard_snapshot_exists(self):
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        wizard_document = wizard.current_document_id
        wizard_value = wizard_document.value_ids[:1]
        self.template.unlink()
        self.assertFalse(wizard.template_id)
        self.assertFalse(wizard_document.source_document_id)
        self.assertFalse(wizard_value.source_field_id)
        self.assertTrue(wizard_document.source_pdf)
