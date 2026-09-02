from odoo.tests.common import TransactionCase


class TestEmployeeContractDmsLink(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.env["dms.storage"].create(
            {"name": "Employee contract storage", "save_type": "database"}
        )
        cls.root_directory = cls.env["dms.directory"].create(
            {
                "name": "Catalog",
                "is_root_directory": True,
                "storage_id": cls.storage.id,
            }
        )
        cls.directory = cls.env["dms.directory"].create(
            {
                "name": "Contracts",
                "parent_id": cls.root_directory.id,
                "storage_id": cls.storage.id,
            }
        )
        cls.dms_file = cls.env["dms.file"].create(
            {
                "name": "employment-contract.pdf",
                "directory_id": cls.directory.id,
                "content_binary": b"Contract content",
            }
        )
        cls.employee = cls.env["hr.employee"].create({"name": "Test Employee"})

    def test_contextual_file_display_name(self):
        self.assertEqual(self.dms_file.display_name, "employment-contract.pdf")
        self.assertEqual(
            self.dms_file.with_context(
                employee_contract_dms_show_path=True
            ).display_name,
            "Catalog / Contracts / employment-contract.pdf",
        )

    def test_create_contract_synchronizes_reference(self):
        contract = self.env["hr.contract"].create(
            {
                "contract_dms_file_id": self.dms_file.id,
                "employee_id": self.employee.id,
                "wage": 100000,
            }
        )

        self.assertEqual(contract.contract_dms_file_id, self.dms_file)
        self.assertEqual(
            contract.name,
            "Catalog / Contracts / employment-contract.pdf",
        )

    def test_onchange_synchronizes_unsaved_contract_reference(self):
        contract = self.env["hr.contract"].new(
            {"contract_dms_file_id": self.dms_file.id}
        )
        contract._onchange_contract_dms_file_id()

        self.assertEqual(
            contract.name,
            "Catalog / Contracts / employment-contract.pdf",
        )

    def test_write_contract_synchronizes_reference(self):
        contract = self.env["hr.contract"].create(
            {
                "name": "Legacy contract reference",
                "employee_id": self.employee.id,
                "wage": 100000,
            }
        )
        contract.write({"contract_dms_file_id": self.dms_file.id})

        self.assertEqual(
            contract.name,
            "Catalog / Contracts / employment-contract.pdf",
        )

    def test_deleted_file_preserves_contract_reference(self):
        contract = self.env["hr.contract"].create(
            {
                "contract_dms_file_id": self.dms_file.id,
                "employee_id": self.employee.id,
                "wage": 100000,
            }
        )
        expected_name = contract.name

        self.dms_file.unlink()

        self.assertFalse(contract.contract_dms_file_id)
        self.assertEqual(contract.name, expected_name)
