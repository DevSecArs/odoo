from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user

from .common import DmsPdfAutocompleteCase


class TestPdfSecurity(DmsPdfAutocompleteCase):
    def test_wizard_owner_is_enforced(self):
        wizard = self.create_wizard()
        other = new_test_user(self.env, login='other-dms-pdf', groups='dms.group_dms_user')
        with self.assertRaises(AccessError):
            wizard.with_user(other)._check_owner()

    def test_multiple_files_are_rejected(self):
        first = self.create_pdf_file()
        second = self.create_pdf_file(name='second-template.pdf')
        with self.assertRaises(ValidationError):
            (first | second).action_dms_pdf_fill()

    def test_batch_limit_is_enforced_server_side(self):
        wizard = self.create_wizard()
        self.env['ir.config_parameter'].set_param('dms_pdf_autocomplete.max_batch_size', 1)
        wizard.partner_ids = self.partner_a | self.partner_b
        with self.assertRaises(ValidationError):
            wizard.action_prepare_mappings()
