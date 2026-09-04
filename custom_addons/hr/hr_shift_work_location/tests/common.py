# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields
from odoo.addons.base.tests.common import BaseCommon


class ShiftWorkLocationCommon(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"shift_start_day": "0", "shift_end_day": "4"})
        cls.calendar = cls.env["resource.calendar"].create(
            {
                "name": "Shift interval calendar",
                "tz": "Europe/Moscow",
                "attendance_ids": [],
            }
        )
        cls.office = cls.env["hr.work.location"].create(
            {
                "name": "Main office",
                "company_id": cls.company.id,
                "location_type": "office",
                "address_id": cls.company.partner_id.id,
            }
        )
        cls.remote = cls.env["hr.work.location"].create(
            {
                "name": "Remote",
                "company_id": cls.company.id,
                "location_type": "home",
                "address_id": cls.company.partner_id.id,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Interval Employee",
                "company_id": cls.company.id,
                "resource_calendar_id": cls.calendar.id,
                "work_location_id": cls.office.id,
                "shift_planning": True,
            }
        )
        cls.other_employee = cls.env["hr.employee"].create(
            {
                "name": "Other Employee",
                "company_id": cls.company.id,
                "resource_calendar_id": cls.calendar.id,
                "work_location_id": cls.office.id,
                "shift_planning": False,
            }
        )
        cls.morning = cls.env["hr.shift.template"].create(
            {
                "name": "Morning",
                "start_time": 9.0,
                "end_time": 14.0,
                "tz": "Europe/Moscow",
                "color": 2,
                "default_work_location_id": cls.office.id,
            }
        )
        cls.evening = cls.env["hr.shift.template"].create(
            {
                "name": "Evening",
                "start_time": 15.0,
                "end_time": 19.0,
                "tz": "Europe/Moscow",
                "color": 4,
                "default_work_location_id": cls.remote.id,
            }
        )
        cls.planning = cls.env["hr.shift.planning"].create(
            {"year": 2025, "week_number": 3, "state": "assignment"}
        )
        cls.shift = cls.env["hr.shift.planning.shift"].create(
            {"planning_id": cls.planning.id, "employee_id": cls.employee.id}
        )
        cls.monday = cls.shift.line_ids.filtered(lambda line: line.day_number == "0")

    def assign_two_monday_intervals(self):
        self.monday.write({"template_id": self.morning.id})
        evening = self.env["hr.shift.planning.line"].create(
            {
                "shift_id": self.shift.id,
                "day_number": "0",
                "template_id": self.evening.id,
            }
        )
        return self.monday, evening

    @classmethod
    def create_user(cls, login, groups):
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.com",
                "company_id": cls.company.id,
                "company_ids": [fields.Command.set(cls.company.ids)],
                "groups_id": [fields.Command.set(groups.ids)],
            }
        )
