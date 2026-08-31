# Copyright 2025 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import datetime

import pytz
from freezegun import freeze_time

from odoo import fields
from odoo.tests import Form
from odoo.tools import mute_logger

from .common import TestHrShiftBase


class TestHrShift(TestHrShiftBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.planning = cls.env["hr.shift.planning"].create(
            {
                "year": 2025,
                "week_number": 3,
                "start_date": "2025-01-13",
                "end_date": "2025-01-19",
            }
        )

    def test_hr_shift_planning_display_name(self):
        self.assertEqual(
            self.planning.display_name, "2025 Week 3 (2025-01-13 - 2025-01-19)"
        )

    def test_delete_shift_and_planning_actions(self):
        self.planning.generate_shifts()
        shift = self.planning.shift_ids[:1]
        shift_lines = shift.line_ids

        reload_action = shift.action_delete_shift()

        self.assertEqual(reload_action["tag"], "reload")
        self.assertFalse(shift.exists())
        self.assertFalse(shift_lines.exists())

        remaining_shifts = self.planning.shift_ids
        remaining_lines = remaining_shifts.line_ids
        planning_action = self.planning.action_delete_planning()

        self.assertEqual(planning_action["res_model"], "hr.shift.planning")
        self.assertFalse(self.planning.exists())
        self.assertFalse(remaining_shifts.exists())
        self.assertFalse(remaining_lines.exists())

    def test_hr_shift_planning_line_incomplete_onchange_values(self):
        """Computed fields must support the partial records created by onchange."""
        line = self.env["hr.shift.planning.line"].new({})

        self.assertEqual(line.display_name, "Unassigned")
        self.assertFalse(line.start_time)
        self.assertFalse(line.end_time)
        self.assertFalse(line.start_date)

    def test_daily_unassignment_is_not_restored_from_weekly_template(self):
        self.planning.generate_shifts()
        shift = self.planning.shift_ids.filtered(
            lambda item: item.employee_id == self.employee_a
        )
        shift.template_id = self.template_morning
        line = shift.line_ids.filtered(lambda item: item.day_number == "3")

        line.action_unassign_shift()

        self.assertFalse(line.template_id)
        self.assertEqual(line.state, "unassigned")
        line_data = next(
            value
            for key, value in shift.lines_data.items()
            if str(key) == str(line.id)
        )
        self.assertEqual(line_data["state"], "unassigned")

    def test_copy_planning_warns_and_skips_employees_on_leave(self):
        self.planning.generate_shifts()
        shift_a = self.planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_a
        )
        shift_b = self.planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_b
        )
        shift_a.template_id = self.template_morning
        shift_b.template_id = self.template_afternoon
        shift_b.line_ids.filtered(
            lambda line: line.day_number == "3"
        ).action_unassign_shift()
        self.env["resource.calendar.leaves"].create(
            {
                "calendar_id": self.employee_a.resource_calendar_id.id,
                "resource_id": self.employee_a.resource_id.id,
                "date_from": "2025-01-20 08:00:00",
                "date_to": "2025-01-20 17:00:00",
            }
        )
        wizard = self.env["shift.planning.wizard"].create(
            {
                "generation_type": "from_planning",
                "from_planning_id": self.planning.id,
                "week_number": 4,
                "year": 2025,
                "copy_shift_details": True,
            }
        )

        warning_action = wizard.generate()

        self.assertEqual(
            warning_action["res_model"], "shift.planning.leave.warning.wizard"
        )
        self.assertFalse(
            self.env["hr.shift.planning"].search(
                [("year", "=", 2025), ("week_number", "=", 4)]
            )
        )
        warning = self.env[warning_action["res_model"]].browse(
            warning_action["res_id"]
        )
        self.assertEqual(warning.employee_ids, self.employee_a)

        planning_action = warning.action_generate_without_employees_on_leave()
        planning = self.env["hr.shift.planning"].browse(planning_action["res_id"])
        copied_shift_a = planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_a
        )
        copied_shift_b = planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_b
        )
        self.assertFalse(copied_shift_a.template_id)
        self.assertFalse(copied_shift_a.line_ids.template_id)
        self.assertEqual(copied_shift_b.template_id, self.template_afternoon)
        self.assertFalse(
            copied_shift_b.line_ids.filtered(
                lambda line: line.day_number == "3"
            ).template_id
        )
        self.assertEqual(
            copied_shift_b.line_ids.filtered(
                lambda line: line.day_number == "0"
            ).template_id,
            self.template_afternoon,
        )

    def test_attendance_intervals_batch(self):
        self.planning.generate_shifts()
        self.planning.shift_ids.line_ids.template_id = self.template_morning
        start_dt = end_dt = datetime(2025, 1, 13, tzinfo=pytz.utc)
        res = self.employee_a.resource_calendar_id._attendance_intervals_batch(
            start_dt, end_dt, resources=self.employee_a.resource_id
        )[self.employee_a.resource_id.id]
        interval = list(res)[0]
        start = interval[0]
        stop = interval[1]
        self.assertEqual(start.date(), fields.Date.from_string("2025-01-13"))
        self.assertEqual(start.hour, 7)
        self.assertEqual(stop.date(), fields.Date.from_string("2025-01-13"))
        self.assertEqual(stop.hour, 13)
        self.assertEqual(interval[2]._name, "hr.shift.planning.line")

    def test_hr_shift_planning_line_leave(self):
        self.env["resource.calendar.leaves"].create(
            {
                "calendar_id": self.employee_a.resource_calendar_id.id,
                "resource_id": self.employee_a.resource_id.id,
                "date_from": "2025-01-13 08:00:00",
                "date_to": "2025-01-13 17:00:00",
            }
        )
        self.planning.generate_shifts()
        shift_a = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        shift_a_line_0 = shift_a.line_ids.filtered(lambda x: x.day_number == "0")
        self.assertEqual(shift_a_line_0.state, "on_leave")
        self.assertFalse(shift_a_line_0.reviewed)
        self.assertTrue(self.planning.issued_shift_ids)
        shift_a.action_toggle_reviewed()
        self.assertFalse(self.planning.issued_shift_ids)
        self.assertTrue(shift_a_line_0.reviewed)
        shift_a_line_1 = shift_a.line_ids.filtered(lambda x: x.day_number == "1")
        self.assertEqual(shift_a_line_1.state, "unassigned")
        self.assertFalse(shift_a.template_id)
        self.assertFalse(shift_a_line_0.template_id)
        self.assertFalse(shift_a_line_1.template_id)
        template_morning = self.env.ref("hr_shift.template_morning")
        shift_a.write({"template_id": template_morning.id})
        self.assertEqual(shift_a.template_id, template_morning)
        self.assertFalse(shift_a_line_0.template_id)
        self.assertFalse(shift_a_line_1.exists())
        shift_a_line_1 = shift_a.line_ids.filtered(lambda x: x.day_number == "1")
        self.assertEqual(shift_a_line_1.template_id, template_morning)

    def test_leave_recomputes_unassigned_lines_and_planning_issues(self):
        self.planning.generate_shifts()
        shift_a = self.planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_a
        )
        monday = shift_a.line_ids.filtered(lambda line: line.day_number == "0")
        self.assertEqual(monday.state, "unassigned")
        self.assertEqual(self.planning.issued_shifts_count, 0)

        leave = self.env["resource.calendar.leaves"].create(
            {
                "calendar_id": self.employee_a.resource_calendar_id.id,
                "resource_id": self.employee_a.resource_id.id,
                "date_from": "2025-01-13 08:00:00",
                "date_to": "2025-01-13 17:00:00",
            }
        )

        self.assertEqual(monday.state, "on_leave")
        self.assertEqual(self.planning.issued_shift_ids, shift_a)
        self.assertEqual(self.planning.issued_shifts_count, 1)

        leave.unlink()

        self.assertEqual(monday.state, "unassigned")
        self.assertFalse(self.planning.issued_shift_ids)
        self.assertEqual(self.planning.issued_shifts_count, 0)

    @mute_logger("odoo.models.unlink")
    def test_hr_shift_planning_full(self):
        self.assertEqual(self.planning.state, "new")
        self.planning.generate_shifts()
        self.assertEqual(self.planning.state, "assignment")
        employees = self.planning.shift_ids.mapped("employee_id")
        self.assertIn(self.employee_a, employees)
        self.assertIn(self.employee_b, employees)
        self.assertNotIn(self.employee_c, employees)
        shift_a = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        self.assertFalse(shift_a.template_id)
        self.assertEqual(len(shift_a.line_ids), 5)
        shift_a_line_0 = shift_a.line_ids.filtered(lambda x: x.day_number == "0")
        self.assertEqual(shift_a_line_0.state, "unassigned")
        shift_a.line_ids.template_id = self.template_morning
        self.assertEqual(shift_a_line_0.state, "assigned")
        self.assertEqual(
            shift_a_line_0.start_date, fields.Date.from_string("2025-01-13")
        )
        self.assertEqual(
            shift_a_line_0.start_time,
            fields.Datetime.from_string("2025-01-13 07:00:00"),
        )
        self.assertEqual(
            shift_a_line_0.end_time, fields.Datetime.from_string("2025-01-13 13:00:00")
        )
        shift_b = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_b
        )
        self.assertFalse(shift_b.template_id)
        self.assertEqual(len(shift_b.line_ids), 5)
        shift_b.line_ids.template_id = self.template_afternoon
        shift_b_line_0 = shift_b.line_ids.filtered(lambda x: x.day_number == "0")
        shift_b_line_0.template_id = self.template_morning
        res = self.planning.copy_to_planning()
        wizard_form = Form(self.env[res["res_model"]].with_context(**res["context"]))
        wizard = wizard_form.save()
        self.assertEqual(wizard.generation_type, "from_planning")
        self.assertEqual(wizard.from_planning_id, self.planning)
        self.assertEqual(wizard.year, 2025)
        self.assertEqual(wizard.week_number, 4)
        wizard_form = Form(self.env["shift.planning.wizard"])
        wizard_form.copy_shift_details = True
        wizard = wizard_form.save()
        self.assertEqual(wizard.generation_type, "from_last")
        self.assertEqual(wizard.from_planning_id, self.planning)
        self.assertEqual(wizard.year, 2025)
        self.assertEqual(wizard.week_number, 4)
        res = wizard.generate()
        planning_extra = self.env[res["res_model"]].browse(res["res_id"])
        self.assertTrue(planning_extra)
        self.assertEqual(planning_extra.state, "assignment")
        employees = planning_extra.shift_ids.mapped("employee_id")
        self.assertIn(self.employee_a, employees)
        self.assertIn(self.employee_b, employees)
        self.assertNotIn(self.employee_c, employees)
        shift_a = planning_extra.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        self.assertFalse(shift_a.template_id)
        self.assertEqual(len(shift_a.line_ids), 5)
        shift_a_line_0 = shift_a.line_ids.filtered(lambda x: x.day_number == "0")
        self.assertEqual(shift_a_line_0.state, "assigned")
        self.assertEqual(shift_a_line_0.template_id, self.template_morning)
        shift_b = planning_extra.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_b
        )
        self.assertFalse(shift_b.template_id)
        self.assertEqual(len(shift_b.line_ids), 5)
        shift_b_line_0 = shift_b.line_ids.filtered(lambda x: x.day_number == "0")
        self.assertEqual(shift_b_line_0.state, "assigned")
        self.assertEqual(shift_b_line_0.template_id, self.template_morning)
        shift_b_line_1 = shift_b.line_ids.filtered(lambda x: x.day_number == "1")
        self.assertEqual(shift_b_line_1.state, "assigned")
        self.assertEqual(shift_b_line_1.template_id, self.template_afternoon)

    @freeze_time("2025-01-13 08:00:00")
    def test_hr_shift_current_shift_id_two_shifts_same_day_morning(self):
        self.planning.generate_shifts()
        shift = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        line_morning = shift.line_ids.filtered(lambda x: x.day_number == "0")
        line_morning.template_id = self.template_morning
        self.env["hr.shift.planning.line"].create(
            {
                "shift_id": shift.id,
                "day_number": "0",
                "template_id": self.template_afternoon.id,
            }
        )
        self.assertEqual(self.employee_a.current_shift_id, line_morning)

    @freeze_time("2025-01-13 14:00:00")
    def test_hr_shift_current_shift_id_two_shifts_same_day_afternoon(self):
        self.planning.generate_shifts()
        shift = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        line_morning = shift.line_ids.filtered(lambda x: x.day_number == "0")
        line_morning.template_id = self.template_morning
        line_afternoon = self.env["hr.shift.planning.line"].create(
            {
                "shift_id": shift.id,
                "day_number": "0",
                "template_id": self.template_afternoon.id,
            }
        )
        self.assertEqual(self.employee_a.current_shift_id, line_afternoon)

    @freeze_time("2025-01-13 20:30:00")
    def test_hr_shift_current_shift_id_two_shifts_same_day_after_both(self):
        self.planning.generate_shifts()
        shift = self.planning.shift_ids.filtered(
            lambda x: x.employee_id == self.employee_a
        )
        line_morning = shift.line_ids.filtered(lambda x: x.day_number == "0")
        line_morning.template_id = self.template_morning
        self.env["hr.shift.planning.line"].create(
            {
                "shift_id": shift.id,
                "day_number": "0",
                "template_id": self.template_afternoon.id,
            }
        )
        self.assertFalse(self.employee_a.current_shift_id)
