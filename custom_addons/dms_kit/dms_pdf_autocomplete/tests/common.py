import base64
import io

from odoo.tests.common import TransactionCase
from odoo.tools import pdf


class DmsPdfAutocompleteCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.env['dms.storage'].create({
            'name': 'PDF Test Storage',
            'save_type': 'database',
        })
        cls.directory = cls.env['dms.directory'].create({
            'name': 'PDF Test Directory',
            'is_root_directory': True,
            'storage_id': cls.storage.id,
        })
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Иван Иванов',
            'email': 'ivan@example.com',
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Пётр Петров',
            'email': 'petr@example.com',
        })

    @staticmethod
    def make_pdf(field_names=('name', 'note'), multiline=False):
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
                pdf.NameObject('/FT'): pdf.NameObject('/Tx'),
                pdf.NameObject('/T'): pdf.createStringObject(field_name),
                pdf.NameObject('/TU'): pdf.createStringObject(f'Label {field_name}'),
                pdf.NameObject('/Rect'): pdf.ArrayObject([
                    pdf.NumberObject(20), pdf.NumberObject(240 - index * 30),
                    pdf.NumberObject(280), pdf.NumberObject(260 - index * 30),
                ]),
                pdf.NameObject('/F'): pdf.NumberObject(4),
                pdf.NameObject('/Ff'): pdf.NumberObject((1 << 12) if multiline else 0),
                pdf.NameObject('/DA'): pdf.createStringObject('/Helv 10 Tf 0 g'),
                pdf.NameObject('/AP'): pdf.DictionaryObject({
                    pdf.NameObject('/N'): appearance_reference,
                }),
            })
            reference = writer._addObject(widget)
            annotations.append(reference)
            form_fields.append(reference)
        page[pdf.NameObject('/Annots')] = annotations
        writer._root_object[pdf.NameObject('/AcroForm')] = pdf.DictionaryObject({
            pdf.NameObject('/Fields'): form_fields,
            pdf.NameObject('/DA'): pdf.createStringObject('/Helv 10 Tf 0 g'),
        })
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()

    def create_pdf_file(self, field_names=('name', 'note'), name='template.pdf'):
        return self.env['dms.file'].create({
            'name': name,
            'directory_id': self.directory.id,
            'content': base64.b64encode(self.make_pdf(field_names)),
        })

    def create_wizard(self, file=None, partners=None):
        file = file or self.create_pdf_file()
        file.action_dms_pdf_fill()
        wizard = self.env['dms.pdf.autocomplete.wizard'].search([
            ('source_file_id', '=', file.id),
            ('owner_user_id', '=', self.env.user.id),
        ], order='id desc', limit=1)
        wizard.write({
            'target_model': 'partner',
            'partner_ids': [(6, 0, (partners or self.partner_a).ids)],
        })
        return wizard
