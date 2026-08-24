from odoo.tests.common import TransactionCase


class TestDmsFileSize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = cls.env["dms.storage"].create(
            {"name": "DMS size test storage", "save_type": "database"}
        )
        cls.directory = cls.env["dms.directory"].create(
            {
                "name": "DMS size test directory",
                "is_root_directory": True,
                "storage_id": cls.storage.id,
            }
        )

    def test_size_is_set_for_direct_binary_upload(self):
        content = b"DMS file content"
        dms_file = self.env["dms.file"].create(
            {
                "name": "upload.txt",
                "directory_id": self.directory.id,
                "content_binary": content,
            }
        )

        self.assertEqual(dms_file.size, len(content))
