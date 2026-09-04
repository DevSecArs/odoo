import io

from odoo.addons.pdf_form_core.services import inspect_pdf, render_pdf
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import pdf


class TestPdfFormService(TransactionCase):
    @staticmethod
    def _make_pdf(
        field_names=('name',), field_type='/Tx', encrypted=False,
        multiline=False, xfa=False, include_acroform=True,
    ):
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
        if include_acroform:
            acroform = pdf.DictionaryObject({
                pdf.NameObject('/Fields'): form_fields,
                pdf.NameObject('/DA'): pdf.createStringObject('/Helv 10 Tf 0 g'),
            })
            if xfa:
                acroform[pdf.NameObject('/XFA')] = pdf.createStringObject('unsupported')
            writer._root_object[pdf.NameObject('/AcroForm')] = acroform
        if encrypted:
            writer.encrypt('secret')
        result = io.BytesIO()
        writer.write(result)
        return result.getvalue()

    @staticmethod
    def _reader(document):
        return pdf.PdfFileReader(io.BytesIO(document), strict=False)

    def test_inspect_one_text_field(self):
        self.assertEqual(inspect_pdf(self._make_pdf()), [{
            'name': 'name',
            'label': 'Label name',
            'multiline': False,
        }])

    def test_inspect_multiple_and_multiline_fields(self):
        fields = inspect_pdf(self._make_pdf(('name', 'notes'), multiline=True))
        self.assertEqual([field['name'] for field in fields], ['name', 'notes'])
        self.assertTrue(all(field['multiline'] for field in fields))

    def test_render_preserves_values_readonly_and_appearance(self):
        rendered = render_pdf(self._make_pdf(('name', 'notes')), {
            'name': 'Иван Иванов',
            'notes': 'Первая строка\nВторая строка',
        }, readonly=True)
        reader = self._reader(rendered)
        annotations = reader.getPage(0)['/Annots']
        self.assertEqual(len(annotations), 2)
        for annotation in annotations:
            widget = annotation.getObject()
            self.assertTrue(int(widget['/Ff']) & 1)
            self.assertTrue(widget['/AP']['/N'])
        self.assertEqual(
            [field['name'] for field in inspect_pdf(rendered)],
            ['name', 'notes'],
        )

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(b'')

    def test_oversized_file_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(), max_size=10)

    def test_false_pdf_signature_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(b'not a pdf')

    def test_damaged_pdf_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(b'%PDF-1.4\nnot a PDF')

    def test_encrypted_pdf_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(encrypted=True))

    def test_pdf_without_acroform_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(include_acroform=False))

    def test_xfa_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(xfa=True))

    def test_non_text_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(field_type='/Btn'))

    def test_duplicate_field_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            inspect_pdf(self._make_pdf(('name', 'name')))

    def test_duplicate_widget_is_rejected(self):
        source = self._make_pdf()
        reader = self._reader(source)
        writer = pdf.PdfFileWriter()
        writer.addPage(reader.getPage(0))
        writer.getPage(0)['/Annots'].append(writer.getPage(0)['/Annots'][0])
        writer._root_object[pdf.NameObject('/AcroForm')] = reader.trailer['/Root']['/AcroForm']
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaises(ValidationError):
            inspect_pdf(stream.getvalue())

    def test_orphan_widget_is_rejected(self):
        source = self._make_pdf()
        reader = self._reader(source)
        writer = pdf.PdfFileWriter()
        writer.addPage(reader.getPage(0))
        writer._root_object[pdf.NameObject('/AcroForm')] = pdf.DictionaryObject({
            pdf.NameObject('/Fields'): pdf.ArrayObject(),
        })
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaises(ValidationError):
            inspect_pdf(stream.getvalue())

    def test_cyclic_parent_hierarchy_is_rejected(self):
        source = self._make_pdf()
        reader = self._reader(source)
        writer = pdf.PdfFileWriter()
        writer.addPage(reader.getPage(0))
        widget = writer.getPage(0)['/Annots'][0].getObject()
        widget[pdf.NameObject('/Parent')] = writer.getPage(0)['/Annots'][0]
        del widget['/T']
        writer._root_object[pdf.NameObject('/AcroForm')] = reader.trailer['/Root']['/AcroForm']
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaises(ValidationError):
            inspect_pdf(stream.getvalue())

    def test_render_rejects_changed_field_set(self):
        with self.assertRaises(ValidationError):
            render_pdf(self._make_pdf(), {'other': 'value'})
