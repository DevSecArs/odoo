import base64
import io
import zipfile

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.addons.hr_recruitment_pdf_renderer.models.offer_attachment_service import (
    OLE_SIGNATURE,
    validate_requested_file,
)

from .common import OfferPdfCase


class TestRequestedFileValidation(OfferPdfCase):
    def test_accepts_supported_containers_and_computes_mimetype(self):
        fixtures = {
            'offer.doc': OLE_SIGNATURE + b'doc',
            'offer.xls': OLE_SIGNATURE + b'xls',
            'offer.ppt': OLE_SIGNATURE + b'ppt',
            'offer.docx': self.make_ooxml('word'),
            'offer.xlsx': self.make_ooxml('xl'),
            'offer.pptx': self.make_ooxml('ppt'),
            'offer.odt': self.make_odf('application/vnd.oasis.opendocument.text'),
            'offer.ods': self.make_odf('application/vnd.oasis.opendocument.spreadsheet'),
            'offer.odp': self.make_odf('application/vnd.oasis.opendocument.presentation'),
            'offer.pdf': self.make_pdf(),
        }
        for filename, content in fixtures.items():
            metadata = validate_requested_file(content, filename.upper())
            self.assertTrue(metadata['mimetype'])
            self.assertEqual(metadata['size'], len(content))
            self.assertEqual(len(metadata['checksum']), 64)

    def test_rejects_spoofed_macro_and_unsafe_archives(self):
        for filename in ('offer.exe', 'offer.zip', 'offer.docm'):
            with self.assertRaises(ValidationError):
                validate_requested_file(b'not a document', filename)

        with self.assertRaises(ValidationError):
            validate_requested_file(b'not a zip', 'offer.docx')
        with self.assertRaises(ValidationError):
            validate_requested_file(b'%PDF-1.4\nnot a PDF', 'offer.pdf')
        with self.assertRaises(ValidationError):
            validate_requested_file(self.make_ooxml('xl'), 'offer.docx')

        macro = io.BytesIO()
        with zipfile.ZipFile(macro, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types>macroEnabled</Types>')
            archive.writestr('word/document.xml', '<document/>')
            archive.writestr('word/vbaProject.bin', b'macro')
        with self.assertRaises(ValidationError):
            validate_requested_file(macro.getvalue(), 'offer.docx')

        traversal = io.BytesIO()
        with zipfile.ZipFile(traversal, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('word/document.xml', '<document/>')
            archive.writestr('../payload', b'x')
        with self.assertRaises(ValidationError):
            validate_requested_file(traversal.getvalue(), 'offer.docx')

        scripted = io.BytesIO()
        with zipfile.ZipFile(scripted, 'w') as archive:
            archive.writestr('mimetype', 'application/vnd.oasis.opendocument.text')
            archive.writestr('content.xml', '<office:scripts><script:script/></office:scripts>')
        with self.assertRaises(ValidationError):
            validate_requested_file(scripted.getvalue(), 'offer.odt')

    def test_normalizes_browser_paths_and_enforces_size(self):
        content = self.make_ooxml('word')
        metadata = validate_requested_file(content, 'C:\\fakepath\\off\x00er.DOCX')
        self.assertEqual(metadata['filename'], 'offer.DOCX')
        metadata = validate_requested_file(self.make_pdf(), 'Офер.pdf')
        self.assertEqual(metadata['filename'], 'Офер.pdf')
        with self.assertRaises(ValidationError):
            validate_requested_file(content, 'offer.docx', max_size=1)

    def test_upload_filename_field_is_writable_for_binary_widget(self):
        view = self.env.ref(
            'hr_recruitment_pdf_renderer.hr_offer_pdf_send_wizard_view_form'
        )
        arch = etree.fromstring(view.arch_db)
        filename_field = arch.xpath(
            "//field[@name='current_uploaded_filename']"
        )
        self.assertEqual(len(filename_field), 1)
        self.assertFalse(filename_field[0].get('readonly'))


class TestRequestedFileWorkflow(OfferPdfCase):
    def setUp(self):
        super().setUp()
        self.template, self.pdf_document = self.create_template_with_document()
        self.applicant = self.env['hr.applicant'].create({
            'candidate_id': self.env['hr.candidate'].create({
                'partner_name': 'Candidate',
                'email_from': 'candidate@example.test',
            }).id,
            'company_id': self.env.company.id,
        })

    def _create_requested(self, **values):
        return self.env['mail.template.offer.pdf.document'].create({
            'name': values.pop('name', 'Offer.docx'),
            'template_id': self.template.id,
            'document_type': 'requested_file',
            **values,
        })

    def test_configuration_defaults_and_conditional_source(self):
        requested = self._create_requested(upload_required=False)
        self.assertEqual(self.pdf_document.document_type, 'fillable_pdf')
        self.assertEqual(requested.document_type, 'requested_file')
        self.assertFalse(requested.pdf_file)
        with self.assertRaises(ValidationError):
            self.env['mail.template.offer.pdf.document'].create({
                'name': 'Missing.pdf',
                'template_id': self.template.id,
            })

    def test_configuration_switch_clears_pdf_and_mapping(self):
        self.pdf_document.write({'document_type': 'requested_file'})
        self.assertFalse(self.pdf_document.pdf_file)
        self.assertFalse(self.pdf_document.pdf_filename)
        self.assertFalse(self.pdf_document.field_ids)
        with self.assertRaises(ValidationError):
            self.pdf_document.write({'document_type': 'fillable_pdf'})

    def test_wizard_orders_pdf_before_requested_and_validates_required_upload(self):
        self.pdf_document.sequence = 99
        requested = self._create_requested(sequence=1)
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        self.assertEqual(wizard.document_ids.mapped('source_document_id'), self.pdf_document + requested)
        wizard.action_next()
        self.assertEqual(wizard.current_document_type, 'requested_file')
        with self.assertRaises(ValidationError):
            wizard.action_done()
        with self.assertRaises(UserError):
            wizard.action_refresh_preview()

    def test_binary_widget_upload_keeps_cyrillic_filename(self):
        self.pdf_document.active = False
        self._create_requested(name='Офер.pdf')
        content = self.make_pdf()
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })

        wizard.write({
            'current_uploaded_file': base64.b64encode(content),
            'current_uploaded_filename': 'Офер.pdf',
        })

        self.assertEqual(wizard.current_document_id.uploaded_filename, 'Офер.pdf')
        self.assertEqual(wizard.current_document_id.uploaded_mimetype, 'application/pdf')
        self.assertEqual(base64.b64decode(wizard.current_document_id.uploaded_file), content)
        wizard.action_save()

    def test_save_resume_and_send_requested_file(self):
        self._create_requested()
        content = self.make_ooxml('word')
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        wizard.action_next()
        wizard.current_document_id.write({
            'uploaded_filename': 'C:\\fakepath\\Offer.DOCX',
            'uploaded_file': base64.b64encode(content),
        })
        wizard.action_save()

        reopened = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        upload = reopened.document_ids.filtered(
            lambda document: document.document_type == 'requested_file'
        )
        self.assertEqual(upload.uploaded_filename, 'Offer.DOCX')
        self.assertEqual(base64.b64decode(upload.uploaded_file), content)
        self.assertEqual(
            upload.uploaded_mimetype,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

        reopened.write({
            'current_document_id': upload.id,
            'current_index': 1,
        })
        mail_count = self.env['mail.mail'].search_count([
            ('res_id', '=', self.applicant.id),
            ('model', '=', 'hr.applicant'),
        ])
        reopened.action_done()
        self.assertEqual(reopened.state, 'sent')
        self.assertFalse(upload.uploaded_file)
        self.assertFalse(self.env['hr.pdf.document.draft']._get_current_draft(self.applicant, self.template))
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', self.applicant.id),
            ('name', '=', 'Offer.DOCX'),
        ])
        self.assertEqual(len(attachment), 1)
        self.assertEqual(base64.b64decode(attachment.datas), content)
        self.assertEqual(
            set(reopened.sent_mail_id.attachment_ids.mapped('name')),
            {'Document.pdf', 'Offer.DOCX'},
        )
        reopened.action_done()
        self.assertEqual(
            self.env['mail.mail'].search_count([
                ('res_id', '=', self.applicant.id),
                ('model', '=', 'hr.applicant'),
            ]),
            mail_count + 1,
        )

    def test_optional_invalid_upload_and_replacement(self):
        self.pdf_document.active = False
        self._create_requested(upload_required=False)
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        upload = wizard.current_document_id
        with self.assertRaises(ValidationError):
            upload.write({
                'uploaded_filename': 'fake.docx',
                'uploaded_file': base64.b64encode(b'not a zip'),
            })
        first = self.make_ooxml('word')
        second = self.make_ooxml('word') + b'changed'
        upload.write({
            'uploaded_filename': 'first.docx',
            'uploaded_file': base64.b64encode(first),
        })
        attachment_domain = [
            ('res_model', '=', upload._name),
            ('res_field', '=', 'uploaded_file'),
            ('res_id', '=', upload.id),
        ]
        attachment = self.env['ir.attachment'].search(attachment_domain)
        self.assertEqual(len(attachment), 1)
        upload.write({
            'uploaded_filename': 'second.docx',
            'uploaded_file': base64.b64encode(second),
        })
        self.assertEqual(self.env['ir.attachment'].search(attachment_domain), attachment)
        self.assertEqual(base64.b64decode(upload.uploaded_file), second)

    def test_optional_empty_upload_is_skipped(self):
        self.pdf_document.active = False
        self._create_requested(upload_required=False)
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.applicant.id,
            'template_id': self.template.id,
        })
        wizard.action_done()
        self.assertEqual(wizard.state, 'sent')
