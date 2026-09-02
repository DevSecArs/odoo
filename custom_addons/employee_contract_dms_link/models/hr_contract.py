from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    contract_dms_file_id = fields.Many2one(
        comodel_name="dms.file",
        string="Contract Link",
        copy=False,
        ondelete="set null",
        tracking=True,
    )

    def _get_contract_dms_path(self, file_id):
        """Return the readable catalog path without bypassing DMS access rules."""
        dms_file = self.env["dms.file"].browse(file_id).exists()
        if not dms_file:
            return False
        dms_file.check_access("read")
        return dms_file.with_context(
            employee_contract_dms_show_path=True
        ).display_name

    @api.onchange("contract_dms_file_id")
    def _onchange_contract_dms_file_id(self):
        for contract in self.filtered("contract_dms_file_id"):
            contract.name = contract.contract_dms_file_id.with_context(
                employee_contract_dms_show_path=True
            ).display_name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("contract_dms_file_id") and not vals.get("name"):
                vals["name"] = self._get_contract_dms_path(
                    vals["contract_dms_file_id"]
                )
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("contract_dms_file_id") and "name" not in vals:
            vals["name"] = self._get_contract_dms_path(
                vals["contract_dms_file_id"]
            )
        return super().write(vals)
