from odoo.exceptions import ValidationError

from .common import DmsPdfAutocompleteCase


class TestFieldResolver(DmsPdfAutocompleteCase):
    def setUp(self):
        super().setUp()
        self.resolver = self.env['dms.pdf.value.resolver']

    def test_char(self):
        self.assertEqual(self.resolver.resolve(self.partner_a, 'partner', 'name'), 'Иван Иванов')

    def test_many2one_chain(self):
        self.partner_a.company_id = self.env.company
        self.assertEqual(
            self.resolver.resolve(self.partner_a, 'partner', 'company_id.name'),
            self.env.company.name,
        )

    def test_selection_uses_label(self):
        self.partner_a.company_type = 'company'
        self.assertEqual(self.resolver.resolve(self.partner_a, 'partner', 'company_type'), 'Company')

    def test_boolean_is_text(self):
        self.assertEqual(self.resolver.resolve(self.partner_a, 'partner', 'active'), 'Yes')

    def test_many2many_joins_display_names(self):
        tag_a = self.env['res.partner.category'].create({'name': 'A'})
        tag_b = self.env['res.partner.category'].create({'name': 'B'})
        self.partner_a.category_id = tag_a | tag_b
        self.assertEqual(self.resolver.resolve(self.partner_a, 'partner', 'category_id'), 'A, B')

    def test_invalid_path_is_rejected(self):
        for path in ('_name', 'name()', 'name..x', 'missing'):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                self.resolver.validate_path('partner', path)

    def test_binary_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.resolver.validate_path('partner', 'image_1920')

    def test_non_relational_intermediate_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.resolver.validate_path('partner', 'name.foo')
