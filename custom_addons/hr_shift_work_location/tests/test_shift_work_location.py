# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from datetime import datetime

import pytz

from odoo.exceptions import AccessError, ValidationError

from ..hooks import post_init_hook
from .common import ShiftWorkLocationCommon


class TestShiftWorkLocation(ShiftWorkLocationCommon):
    def test_weekly_hours_exclude_marked_templates(self):
        _morning, evening = self.assign_two_monday_intervals()
        self.assertEqual(self.shift.weekly_planned_hours, 9.0)

        self.evening.exclude_from_planned_hours = True
        self.assertEqual(self.shift.weekly_planned_hours, 5.0)
        self.assertEqual(evening.weekly_planned_hours, 5.0)

        self.morning.exclude_from_planned_hours = True
        self.assertEqual(self.shift.weekly_planned_hours, 0.0)

        self.evening.exclude_from_planned_hours = False
        self.assertEqual(self.shift.weekly_planned_hours, 4.0)

    def test_weekly_planned_hours_follow_interval_changes(self):
        self.monday.write({"template_id": self.morning.id})
        self.assertEqual(self.shift.weekly_planned_hours, 5.0)
        evening = self.env["hr.shift.planning.line"].create(
            {
                "shift_id": self.shift.id,
                "day_number": "0",
                "template_id": self.evening.id,
            }
        )
        self.assertEqual(self.shift.weekly_planned_hours, 9.0)
        self.assertEqual(evening.weekly_planned_hours, 9.0)

        evening.hour_to = 20.0
        self.assertEqual(self.shift.weekly_planned_hours, 10.0)
        self.assertEqual(evening.weekly_planned_hours, 10.0)

        evening.unlink()
        self.assertEqual(self.shift.weekly_planned_hours, 5.0)

    def test_weekdays_use_hr_shift_translation(self):
        if not self.env["res.lang"]._lang_get("ru_RU"):
            self.skipTest("Russian is not enabled in the test database")
        shift = self.shift.with_context(lang="ru_RU")
        shift.invalidate_recordset(["schedule_intervals_data"])

        self.assertEqual(
            shift.schedule_intervals_data["0"]["day"], "Понедельник"
        )

    def test_shift_details_action_provides_creation_defaults(self):
        action = self.shift.action_view_shift_details()

        self.assertEqual(action["context"]["default_shift_id"], self.shift.id)

    def test_template_defaults_and_explicit_values(self):
        self.monday.write({"template_id": self.morning.id})
        self.assertEqual(self.monday.hour_from, 9.0)
        self.assertEqual(self.monday.hour_to, 14.0)
        self.assertEqual(self.monday.work_location_id, self.office)

        tuesday = self.shift.line_ids.filtered(lambda line: line.day_number == "1")
        tuesday.write(
            {
                "template_id": self.morning.id,
                "hour_from": 10.0,
                "hour_to": 13.0,
                "work_location_id": self.remote.id,
            }
        )
        self.assertEqual((tuesday.hour_from, tuesday.hour_to), (10.0, 13.0))
        self.assertEqual(tuesday.work_location_id, self.remote)

    def test_employee_location_fallback(self):
        template = self.env["hr.shift.template"].create(
            {"name": "No location", "start_time": 8.0, "end_time": 12.0}
        )
        self.monday.write({"template_id": template.id})
        self.assertEqual(self.monday.work_location_id, self.employee.work_location_id)

    def test_time_computation_uses_fact_hours(self):
        self.monday.write(
            {
                "template_id": self.morning.id,
                "hour_from": 10.0,
                "hour_to": 13.5,
            }
        )
        self.assertEqual(self.monday.start_time, datetime(2025, 1, 13, 7, 0))
        self.assertEqual(self.monday.end_time, datetime(2025, 1, 13, 10, 30))
        self.assertEqual(self.monday.duration_hours, 3.5)

    def test_overlap_rejected_and_touching_allowed(self):
        self.monday.write({"template_id": self.morning.id})
        with self.assertRaises(ValidationError):
            self.env["hr.shift.planning.line"].create(
                {
                    "shift_id": self.shift.id,
                    "day_number": "0",
                    "template_id": self.evening.id,
                    "hour_from": 13.0,
                    "hour_to": 17.0,
                }
            )
        touching = self.env["hr.shift.planning.line"].create(
            {
                "shift_id": self.shift.id,
                "day_number": "0",
                "template_id": self.evening.id,
                "hour_from": 14.0,
                "hour_to": 19.0,
            }
        )
        self.assertTrue(touching)

    def test_invalid_hours_rejected(self):
        for hour_from, hour_to in [(-1.0, 4.0), (9.0, 9.0), (9.0, 25.0)]:
            with self.assertRaises(ValidationError):
                self.monday.write(
                    {
                        "template_id": self.morning.id,
                        "hour_from": hour_from,
                        "hour_to": hour_to,
                    }
                )

    def test_other_company_location_rejected(self):
        self.env.cr.execute(
            """
            SELECT is_nullable
              FROM information_schema.columns
             WHERE table_name = 'res_company'
               AND column_name = 'security_lead'
            """
        )
        security_lead_column = self.env.cr.fetchone()
        if (
            security_lead_column == ("NO",)
            and "security_lead" not in self.env["res.company"]._fields
        ):
            self.skipTest(
                "The test database has an orphan NOT NULL company column."
            )
        company = self.env["res.company"].create({"name": "Other company"})
        location = self.env["hr.work.location"].create(
            {
                "name": "Other office",
                "company_id": company.id,
                "location_type": "office",
                "address_id": company.partner_id.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.monday.write(
                {"template_id": self.morning.id, "work_location_id": location.id}
            )

    def test_review_and_reset(self):
        _morning, evening = self.assign_two_monday_intervals()
        self.shift.action_toggle_reviewed()
        self.assertTrue(self.shift.reviewed)
        self.monday.write({"hour_from": 8.5})
        self.assertFalse(self.shift.reviewed)
        self.shift.action_toggle_reviewed()
        evening.unlink()
        self.assertFalse(self.shift.reviewed)

    def test_empty_or_locationless_schedule_cannot_be_reviewed(self):
        with self.assertRaises(ValidationError):
            self.shift.action_toggle_reviewed()
        template = self.env["hr.shift.template"].create(
            {"name": "Location required", "start_time": 9.0, "end_time": 14.0}
        )
        self.employee.work_location_id = False
        self.monday.write({"template_id": template.id})
        with self.assertRaises(ValidationError):
            self.shift.action_toggle_reviewed()

    def test_own_editor_security(self):
        own_group = self.env.ref("hr_shift.group_shift_own_editor")
        user = self.create_user("own_shift_editor", own_group)
        self.employee.user_id = user
        self.monday.write({"template_id": self.morning.id})
        self.monday.with_user(user).write({"hour_from": 9.5})
        self.assertEqual(self.monday.hour_from, 9.5)

        other_shift = self.env["hr.shift.planning.shift"].create(
            {"planning_id": self.planning.id, "employee_id": self.other_employee.id}
        )
        with self.assertRaises(AccessError):
            self.env["hr.shift.planning.line"].with_user(user).create(
                {
                    "shift_id": other_shift.id,
                    "day_number": "0",
                    "template_id": self.morning.id,
                }
            )
        with self.assertRaises(AccessError):
            self.shift.with_user(user).action_toggle_reviewed()

    def test_internal_user_without_editor_group_cannot_write(self):
        user = self.create_user("shift_reader", self.env.ref("base.group_user"))
        self.employee.user_id = user
        self.monday.write({"template_id": self.morning.id})
        with self.assertRaises(AccessError):
            self.monday.with_user(user).write({"hour_from": 9.5})

    def test_current_shift_respects_gap_and_boundaries(self):
        morning, evening = self.assign_two_monday_intervals()
        self.assertEqual(
            self.employee._shift_of_date(
                datetime(2025, 1, 13, 9, 0), datetime(2025, 1, 13, 9, 0)
            ),
            morning,
        )
        self.assertFalse(
            self.employee._shift_of_date(
                datetime(2025, 1, 13, 11, 30), datetime(2025, 1, 13, 11, 30)
            )
        )
        self.assertEqual(
            self.employee._shift_of_date(
                datetime(2025, 1, 13, 12, 0), datetime(2025, 1, 13, 12, 0)
            ),
            evening,
        )

    def test_partial_leave_only_blocks_intersection(self):
        morning, evening = self.assign_two_monday_intervals()
        self.env["resource.calendar.leaves"].create(
            {
                "calendar_id": self.calendar.id,
                "resource_id": self.employee.resource_id.id,
                "date_from": datetime(2025, 1, 13, 7, 0),
                "date_to": datetime(2025, 1, 13, 8, 0),
            }
        )
        self.assertEqual(morning.state, "on_leave")
        self.assertEqual(evening.state, "assigned")

    def test_attendance_keeps_two_intervals_and_gap(self):
        self.assign_two_monday_intervals()
        start = datetime(2025, 1, 13, tzinfo=pytz.UTC)
        intervals = list(
            self.calendar._attendance_intervals_batch(
                start,
                start,
                resources=self.employee.resource_id,
                tz=pytz.UTC,
            )[self.employee.resource_id.id]
        )
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0][1].hour, 11)
        self.assertEqual(intervals[1][0].hour, 12)

    def test_copy_preserves_all_intervals_and_resets_review(self):
        self.assign_two_monday_intervals()
        self.shift.action_toggle_reviewed()
        wizard = self.env["shift.planning.wizard"].create(
            {
                "generation_type": "from_planning",
                "from_planning_id": self.planning.id,
                "week_number": 4,
                "year": 2025,
                "copy_shift_details": True,
            }
        )
        action = wizard.generate()
        target = self.env["hr.shift.planning"].browse(action["res_id"])
        copied_shift = target.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee
        )
        monday_lines = copied_shift.line_ids.filtered(
            lambda line: line.day_number == "0" and line.template_id
        ).sorted("hour_from")
        self.assertEqual(len(monday_lines), 2)
        self.assertEqual(monday_lines.mapped("hour_from"), [9.0, 15.0])
        self.assertEqual(monday_lines.work_location_id, self.office | self.remote)
        self.assertFalse(copied_shift.reviewed)

    def test_copy_without_details_keeps_standard_flow(self):
        self.monday.write({"template_id": self.morning.id})
        wizard = self.env["shift.planning.wizard"].create(
            {
                "generation_type": "from_planning",
                "from_planning_id": self.planning.id,
                "week_number": 4,
                "year": 2025,
                "copy_shift_details": False,
            }
        )
        action = wizard.generate()
        self.assertEqual(action["res_model"], "hr.shift.planning")

    def test_unreviewed_copy_warns(self):
        self.monday.write({"template_id": self.morning.id})
        self.planning.state = "planned"
        wizard = self.env["shift.planning.wizard"].create(
            {
                "generation_type": "from_planning",
                "from_planning_id": self.planning.id,
                "week_number": 4,
                "year": 2025,
                "copy_shift_details": True,
            }
        )
        action = wizard.generate()
        self.assertEqual(action["res_model"], "shift.planning.leave.warning.wizard")
        warning = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(warning.unreviewed_employee_ids, self.employee)

    def test_post_init_hook_is_idempotent(self):
        self.monday.write(
            {
                "template_id": self.morning.id,
                "hour_from": 10.0,
                "hour_to": 12.0,
                "work_location_id": self.remote.id,
            }
        )
        post_init_hook(self.env)
        self.assertEqual((self.monday.hour_from, self.monday.hour_to), (10.0, 12.0))
        self.assertEqual(self.monday.work_location_id, self.remote)

    def test_dst_gap_has_controlled_error(self):
        planning = self.env["hr.shift.planning"].create(
            {"year": 2025, "week_number": 13, "state": "assignment"}
        )
        shift = self.env["hr.shift.planning.shift"].create(
            {"planning_id": planning.id, "employee_id": self.other_employee.id}
        )
        template = self.env["hr.shift.template"].create(
            {
                "name": "DST gap",
                "start_time": 2.5,
                "end_time": 3.5,
                "tz": "Europe/Brussels",
                "default_work_location_id": self.office.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["hr.shift.planning.line"].create(
                {
                    "shift_id": shift.id,
                    "day_number": "6",
                    "template_id": template.id,
                }
            )
