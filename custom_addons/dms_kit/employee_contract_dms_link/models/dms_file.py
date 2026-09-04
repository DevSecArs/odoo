from odoo import api, models


class DmsFile(models.Model):
    _inherit = "dms.file"

    @api.depends("name", "directory_id.complete_name")
    @api.depends_context("employee_contract_dms_show_path")
    def _compute_display_name(self):
        """Show the full DMS path only in the employee contract field."""
        if not self.env.context.get("employee_contract_dms_show_path"):
            return super()._compute_display_name()

        for record in self:
            path_parts = (record.directory_id.complete_name, record.name)
            record.display_name = " / ".join(filter(None, path_parts))

    @api.depends("name", "directory_id", "directory_id.parent_path")
    def _compute_path(self):
        """Keep DMS breadcrumbs independent from contextual display names."""
        return super(
            DmsFile,
            self.with_context(employee_contract_dms_show_path=False),
        )._compute_path()
