import base64

from .common import DmsPdfAutocompleteCase


class TestDmsPdfConfiguration(DmsPdfAutocompleteCase):
    def test_regular_pdf_is_not_validated_on_upload(self):
        file = self.env['dms.file'].create({
            'name': 'ordinary.pdf',
            'directory_id': self.directory.id,
            'content': base64.b64encode(b'%PDF-1.4\nordinary'),
        })
        self.assertEqual(file.pdf_form_state, 'not_checked')

    def test_fill_synchronizes_fields(self):
        file = self.create_pdf_file()
        file.action_dms_pdf_fill()
        self.assertEqual(file.pdf_form_state, 'valid')
        self.assertTrue(file.pdf_form_enabled)
        self.assertEqual(set(file.pdf_form_field_ids.mapped('pdf_field_name')), {'name', 'note'})

    def test_invalid_pdf_records_safe_state(self):
        file = self.env['dms.file'].create({
            'name': 'broken.pdf',
            'directory_id': self.directory.id,
            'content': base64.b64encode(b'%PDF-1.4\nbroken'),
        })
        action = file.action_dms_pdf_fill()
        self.assertEqual(file.pdf_form_state, 'invalid')
        self.assertEqual(action['tag'], 'display_notification')

    def test_replacement_keeps_matching_fields(self):
        file = self.create_pdf_file(('name', 'old'))
        file.action_dms_pdf_fill()
        name_field = file.pdf_form_field_ids.filtered(lambda item: item.pdf_field_name == 'name')
        name_field.label = 'Custom label'
        file.content = base64.b64encode(self.make_pdf(('name', 'new')))
        self.assertEqual(file.pdf_form_state, 'not_checked')
        file.action_dms_pdf_fill()
        self.assertEqual(name_field.label, 'Custom label')
        self.assertFalse(file.pdf_form_field_ids.filtered(lambda item: item.pdf_field_name == 'old').active)
        self.assertTrue(file.pdf_form_field_ids.filtered(lambda item: item.pdf_field_name == 'new').active)

    def test_mappings_are_independent_by_target(self):
        file = self.create_pdf_file(('name',))
        file.action_dms_pdf_fill()
        field = file.pdf_form_field_ids
        employee = self.env['dms.pdf.field.mapping'].create({
            'form_field_id': field.id,
            'target_model': 'employee',
            'fill_mode': 'odoo_field',
            'source_field_path': 'name',
        })
        partner = self.env['dms.pdf.field.mapping'].create({
            'form_field_id': field.id,
            'target_model': 'partner',
            'fill_mode': 'manual',
        })
        self.assertNotEqual(employee.target_model, partner.target_model)
