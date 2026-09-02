# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    def _shift_of_date(self, min_time, max_time):
        """Use half-open intervals so adjacent shifts are never both current."""
        return self.env["hr.shift.planning.line"].sudo().search(
            [
                ("employee_id", "=", self.id),
                ("state", "=", "assigned"),
                ("start_time", "<=", max_time),
                ("end_time", ">", min_time),
            ],
            order="start_time, id",
        )
