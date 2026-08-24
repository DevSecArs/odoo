import base64

from odoo import api, models


class DmsFile(models.Model):
    _inherit = "dms.file"

    def _recompute_content_size(self):
        """Store the byte size represented by the file content.

        The DMS upload controller creates records with ``content_binary``
        directly.  That bypasses the inverse method of ``content``, which is
        where DMS normally fills ``size``.  Read the unified ``content`` field
        so this also works for database, filestore, and attachment storage.
        """
        for record in self:
            content = record.with_context(base64=True).content
            content_size = len(base64.b64decode(content or b""))
            if record.size != content_size:
                record.write({"size": content_size})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._recompute_content_size()
        return records

    def write(self, vals):
        result = super().write(vals)
        content_fields = {"content", "content_binary", "content_file", "attachment_id"}
        if content_fields.intersection(vals):
            self._recompute_content_size()
        return result
