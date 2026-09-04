import base64
import io
import zipfile

from odoo.tests.common import TransactionCase
from odoo.tools import pdf


class OfferPdfCase(TransactionCase):
    @staticmethod
    def make_ooxml(kind='word'):
        """Create a minimal OOXML container for upload validation tests."""
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                '[Content_Types].xml',
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
            archive.writestr(f'{kind}/document.xml', '<document/>')
        return result.getvalue()

    @staticmethod
    def make_odf(mimetype='application/vnd.oasis.opendocument.text'):
        """Create a minimal OpenDocument container for upload validation tests."""
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as archive:
            archive.writestr('mimetype', mimetype, compress_type=zipfile.ZIP_STORED)
            archive.writestr('content.xml', '<office:document/>')
        return result.getvalue()

    @staticmethod
    def make_pdf(field_names=('candidate_name', 'candidate_address'), field_type='/Tx', encrypted=False):
        """Create a small AcroForm fixture without relying on a user file."""
        writer = pdf.PdfFileWriter()
        writer.addBlankPage(width=300, height=300)
        page = writer.getPage(0)
        annotations = pdf.ArrayObject()
        form_fields = pdf.ArrayObject()
        for index, field_name in enumerate(field_names):
            appearance = pdf.DecodedStreamObject()
            appearance.setData(b'q Q')
            appearance.update({
                pdf.NameObject('/Type'): pdf.NameObject('/XObject'),
                pdf.NameObject('/Subtype'): pdf.NameObject('/Form'),
                pdf.NameObject('/BBox'): pdf.ArrayObject([
                    pdf.NumberObject(0), pdf.NumberObject(0),
                    pdf.NumberObject(260), pdf.NumberObject(20),
                ]),
            })
            appearance_reference = writer._addObject(appearance)
            widget = pdf.DictionaryObject({
                pdf.NameObject('/Type'): pdf.NameObject('/Annot'),
                pdf.NameObject('/Subtype'): pdf.NameObject('/Widget'),
                pdf.NameObject('/FT'): pdf.NameObject(field_type),
                pdf.NameObject('/T'): pdf.createStringObject(field_name),
                pdf.NameObject('/Rect'): pdf.ArrayObject([
                    pdf.NumberObject(20), pdf.NumberObject(240 - index * 30),
                    pdf.NumberObject(280), pdf.NumberObject(260 - index * 30),
                ]),
                pdf.NameObject('/F'): pdf.NumberObject(4),
                pdf.NameObject('/Ff'): pdf.NumberObject(0),
                pdf.NameObject('/DA'): pdf.createStringObject('/Helv 10 Tf 0 g'),
                pdf.NameObject('/AP'): pdf.DictionaryObject({
                    pdf.NameObject('/N'): appearance_reference,
                }),
            })
            reference = writer._addObject(widget)
            annotations.append(reference)
            form_fields.append(reference)
        page[pdf.NameObject('/Annots')] = annotations
        writer._root_object.update({pdf.NameObject('/AcroForm'): pdf.DictionaryObject({
            pdf.NameObject('/Fields'): form_fields,
            pdf.NameObject('/DA'): pdf.createStringObject('/Helv 10 Tf 0 g'),
        })})
        result = io.BytesIO()
        if encrypted:
            writer.encrypt('secret')
        writer.write(result)
        return result.getvalue()

    def create_template_with_document(self, document_bytes=None):
        template = self.env['mail.template'].create({
            'name': 'PDF documents',
            'model_id': self.env['ir.model']._get('hr.applicant').id,
            'subject': 'Document',
            'body_html': '<p>Hello</p>',
            'offer_pdf_manual_enabled': True,
            'offer_pdf_company_id': self.env.company.id,
        })
        document = self.env['mail.template.offer.pdf.document'].create({
            'name': 'Document.pdf',
            'template_id': template.id,
            'pdf_filename': 'document.pdf',
            'pdf_file': base64.b64encode(document_bytes or self.make_pdf()),
        })
        return template, document
