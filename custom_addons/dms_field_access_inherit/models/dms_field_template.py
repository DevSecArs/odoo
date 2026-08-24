from odoo import models


class DmsFieldTemplate(models.Model):
    _inherit = "dms.field.template"

    def _prepare_directory_vals(self, directory, record):
        """Keep parent access groups on embedded record directories."""
        vals = super()._prepare_directory_vals(directory, record)
        if self.parent_directory_id:
            vals["inherit_group_ids"] = True
        return vals
