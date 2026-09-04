import base64

from odoo.exceptions import ValidationError
from odoo.addons.hr_recruitment_pdf_renderer.models.offer_pdf_service import inspect_pdf, render_pdf

from .common import OfferPdfCase


class TestOfferPdfValidation(OfferPdfCase):
    def test_valid_pdf_and_mapping_sync(self):
        template, document = self.create_template_with_document()
        self.assertEqual(document.validation_state, 'valid')
        self.assertEqual(document.field_ids.mapped('pdf_field_name'), ['candidate_name', 'candidate_address'])
        document.field_ids.filtered(lambda field: field.pdf_field_name == 'candidate_name').default_source = 'candidate_name'
        document.pdf_file = base64.b64encode(self.make_pdf(('candidate_name', 'job_name')))
        self.assertEqual(document.field_ids.filtered(lambda field: field.pdf_field_name == 'candidate_name').default_source, 'candidate_name')
        self.assertFalse(document.field_ids.filtered(lambda field: field.pdf_field_name == 'candidate_address').active)
        self.assertTrue(template.offer_pdf_document_ids)

    def test_reject_invalid_forms(self):
        invalid_documents = [
            b'%PDF-1.4\nnot a PDF',
            self.make_pdf((), encrypted=False),
            self.make_pdf(('checkbox',), field_type='/Btn'),
            self.make_pdf(('unsafe name',)),
            self.make_pdf(encrypted=True),
        ]
        for document in invalid_documents:
            with self.assertRaises(ValidationError):
                inspect_pdf(document)

    def test_rendered_pdf_is_read_only_and_keeps_values(self):
        source = self.make_pdf()
        rendered = render_pdf(source, {
            'candidate_name': 'Иванов Иван Иванович',
            'candidate_address': 'г. Москва, ул. Пример, д. 1',
        }, readonly=True)
        self.assertNotEqual(source, rendered)
        self.assertEqual(
            [field['name'] for field in inspect_pdf(rendered)],
            ['candidate_name', 'candidate_address'],
        )
