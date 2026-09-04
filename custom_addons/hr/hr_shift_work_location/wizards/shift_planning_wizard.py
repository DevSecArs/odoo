# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models


class ShiftPlanningWizard(models.TransientModel):
    _inherit = "shift.planning.wizard"

    def _get_unreviewed_employees(self):
        self.ensure_one()
        if self.from_planning_id.state != "planned":
            return self.env["hr.employee"]
        shifts = self.from_planning_id.shift_ids.filtered(
            lambda shift: shift.line_ids.filtered("template_id") and not shift.reviewed
        )
        return shifts.employee_id

    def _action_copy_warning(self, employees_on_leave, unreviewed_employees):
        warning = self.env["shift.planning.leave.warning.wizard"].create(
            {
                "planning_wizard_id": self.id,
                "employee_ids": [fields.Command.set(employees_on_leave.ids)],
                "unreviewed_employee_ids": [
                    fields.Command.set(unreviewed_employees.ids)
                ],
            }
        )
        view = self.env.ref("hr_shift.shift_planning_leave_warning_wizard_form")
        return {
            "type": "ir.actions.act_window",
            "name": _("Shift copy warning"),
            "res_model": warning._name,
            "res_id": warning.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
        }

    def generate(self):
        self.ensure_one()
        if not self.copy_shift_details:
            return super().generate()

        employees_on_leave = self._get_employees_on_leave()
        unreviewed_employees = self._get_unreviewed_employees()
        warning_needed = (
            employees_on_leave
            and "skip_leave_employee_ids" not in self.env.context
        ) or (
            unreviewed_employees
            and "skip_unreviewed_employee_ids" not in self.env.context
        )
        if warning_needed:
            return self._action_copy_warning(
                employees_on_leave, unreviewed_employees
            )

        skipped_ids = set(self.env.context.get("skip_leave_employee_ids", []))
        skipped_ids.update(self.env.context.get("skip_unreviewed_employee_ids", []))
        action = super(
            ShiftPlanningWizard,
            self.with_context(skip_leave_employee_ids=list(skipped_ids)),
        ).generate()
        if action.get("res_model") != "hr.shift.planning" or not action.get("res_id"):
            return action

        target_planning = self.env["hr.shift.planning"].browse(action["res_id"])
        target_by_employee = {
            shift.employee_id.id: shift for shift in target_planning.shift_ids
        }
        for source_shift in self.from_planning_id.shift_ids.filtered("reviewed"):
            if source_shift.employee_id.id in skipped_ids:
                continue
            target_shift = target_by_employee.get(source_shift.employee_id.id)
            if target_shift:
                source_shift._copy_reviewed_intervals_to(target_shift)
        return action


class ShiftPlanningLeaveWarningWizard(models.TransientModel):
    _inherit = "shift.planning.leave.warning.wizard"

    unreviewed_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="shift_planning_warning_unreviewed_employee_rel",
        readonly=True,
    )

    def action_generate_without_employees_on_leave(self):
        self.ensure_one()
        return self.planning_wizard_id.with_context(
            skip_leave_employee_ids=self.employee_ids.ids,
            skip_unreviewed_employee_ids=self.unreviewed_employee_ids.ids,
        ).generate()
