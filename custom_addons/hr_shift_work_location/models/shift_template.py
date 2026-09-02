# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ShiftTemplate(models.Model):
    _inherit = "hr.shift.template"

    exclude_from_planned_hours = fields.Boolean(string="Do Not Count Hours")
    default_work_location_id = fields.Many2one(
        comodel_name="hr.work.location",
        string="Default Work Location",
        domain="[('company_id', 'in', allowed_company_ids)]",
    )

    @api.constrains("start_time", "end_time")
    def _check_work_location_interval(self):
        for template in self:
            if not 0 <= template.start_time < template.end_time <= 24:
                raise ValidationError(
                    _(
                        "Shift hours must satisfy 0 <= start time < end time <= 24. "
                        "Intervals crossing midnight are not supported."
                    )
                )
