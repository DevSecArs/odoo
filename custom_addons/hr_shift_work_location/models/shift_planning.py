# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.hr_shift.models.shift_template import WEEK_DAYS_SELECTION


SIGNIFICANT_LINE_FIELDS = {
    "template_id",
    "day_number",
    "hour_from",
    "hour_to",
    "work_location_id",
}


class ShiftPlanning(models.Model):
    _inherit = "hr.shift.planning"

    pending_review_shifts_count = fields.Integer(
        string="Pending review", compute="_compute_pending_review_shifts_count"
    )

    @api.depends("shift_ids.reviewed", "shift_ids.line_ids")
    def _compute_pending_review_shifts_count(self):
        for planning in self:
            planning.pending_review_shifts_count = len(
                planning.shift_ids.filtered(lambda shift: not shift.reviewed)
            )

    def action_view_pending_review_shifts(self):
        self.ensure_one()
        action = self.action_view_shifts()
        action["domain"] = [
            ("planning_id", "=", self.id),
            ("reviewed", "=", False),
        ]
        action["display_name"] = _("Pending review")
        return action


class ShiftPlanningShift(models.Model):
    _inherit = "hr.shift.planning.shift"

    reviewed = fields.Boolean(help="Schedule reviewed by an HR manager")
    schedule_intervals_data = fields.Serialized(
        default={}, compute="_compute_schedule_intervals_data"
    )

    @api.depends(
        "line_ids.day_number",
        "line_ids.template_id",
        "line_ids.state",
        "line_ids.color",
        "line_ids.hour_from",
        "line_ids.hour_to",
        "line_ids.work_location_id",
        "line_ids.work_location_type",
    )
    def _compute_schedule_intervals_data(self):
        weekday_by_number = dict(WEEK_DAYS_SELECTION)
        for shift in self:
            days = defaultdict(list)
            for line in shift.line_ids.sorted(
                key=lambda item: (int(item.day_number or 0), item.hour_from, item.id)
            ):
                state_css_class = {
                    "holiday": "btn-dark",
                    "on_leave": "btn-danger",
                    "unassigned": "btn-light",
                }.get(line.state, f"o_button_color_{line.color}")
                days[line.day_number].append(
                    {
                        "id": line.id,
                        "state": line.state,
                        "template": line.template_id.name,
                        "color": line.color,
                        "hour_from": line.hour_from,
                        "hour_to": line.hour_to,
                        "hour_from_display": line._format_float_hour(line.hour_from),
                        "hour_to_display": line._format_float_hour(line.hour_to),
                        "work_location": line.work_location_id.name,
                        "work_location_type": line.work_location_type,
                        "css_class": state_css_class,
                    }
                )
            shift.schedule_intervals_data = {
                day_number: {
                    "day": _(weekday_by_number.get(day_number)),
                    "intervals": intervals,
                }
                for day_number, intervals in sorted(days.items())
            }

    @api.depends("line_ids.reviewed")
    def _compute_reviewed(self):
        for shift in self:
            shift.reviewed = bool(shift.line_ids) and all(
                shift.line_ids.mapped("reviewed")
            )

    def _inverse_reviewed(self):
        if self.env.context.get("shift_review_confirmation"):
            return super()._inverse_reviewed()
        if any(shift.reviewed for shift in self) and not self.env.user.has_group(
            "hr_shift.group_shift_manager"
        ):
            raise AccessError(_("Only a Shift Manager can review a schedule."))
        for shift in self:
            shift.line_ids.with_context(shift_review_confirmation=True).write(
                {"reviewed": shift.reviewed}
            )

    def _validate_schedule_for_review(self):
        for shift in self:
            assigned_lines = shift.line_ids.filtered("template_id")
            reviewable_issue_lines = shift.line_ids.filtered(
                lambda line: line.state in {"on_leave", "holiday"}
            )
            if not assigned_lines and not reviewable_issue_lines:
                raise ValidationError(_("An empty schedule cannot be reviewed."))
            assigned_lines._check_interval_values(require_location=True)
            assigned_lines._check_interval_overlap()

    def action_toggle_reviewed(self):
        if not self.env.user.has_group("hr_shift.group_shift_manager"):
            raise AccessError(_("Only a Shift Manager can review a schedule."))
        for shift in self:
            if not shift.reviewed:
                shift._validate_schedule_for_review()
            shift.with_context(shift_review_confirmation=True).reviewed = (
                not shift.reviewed
            )
        return True

    def _copy_reviewed_intervals_to(self, target_shift):
        """Copy every assigned interval while preserving protected target lines."""
        self.ensure_one()
        target_shift.ensure_one()
        source_by_day = defaultdict(list)
        for line in self.line_ids.filtered("template_id").sorted(
            key=lambda item: (int(item.day_number), item.hour_from, item.id)
        ):
            source_by_day[line.day_number].append(
                {
                    "template_id": line.template_id.id,
                    "day_number": line.day_number,
                    "hour_from": line.hour_from,
                    "hour_to": line.hour_to,
                    "work_location_id": line.work_location_id.id,
                    "reviewed": False,
                }
            )
        for day_number, payloads in source_by_day.items():
            target_lines = target_shift.line_ids.filtered(
                lambda line, day=day_number: line.day_number == day
                and line.state not in {"holiday", "on_leave"}
            )
            if not target_lines:
                continue
            first_line = target_lines[:1]
            (target_lines - first_line).unlink()
            first_line.with_context(shift_copy=True).write(payloads[0])
            if len(payloads) > 1:
                self.env["hr.shift.planning.line"].with_context(
                    shift_copy=True
                ).create(
                    [
                        dict(payload, shift_id=target_shift.id)
                        for payload in payloads[1:]
                    ]
                )
        target_shift.line_ids.with_context(shift_review_confirmation=True).write(
            {"reviewed": False}
        )


class ShiftPlanningLine(models.Model):
    _inherit = "hr.shift.planning.line"
    _order = "shift_id desc, day_number asc, hour_from asc, id asc"

    hour_from = fields.Float(string="From")
    hour_to = fields.Float(string="To")
    company_id = fields.Many2one(
        related="employee_id.company_id", store=True, readonly=True
    )
    work_location_id = fields.Many2one(
        comodel_name="hr.work.location",
        string="Work Location",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    work_location_type = fields.Selection(
        related="work_location_id.location_type", store=True
    )

    @api.model
    def _format_float_hour(self, value):
        total_minutes = round(value * 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

    @api.depends(
        "day_number",
        "template_id",
        "state",
        "hour_from",
        "hour_to",
        "work_location_id",
        "employee_id",
    )
    def _compute_display_name(self):
        weekday_by_number = dict(WEEK_DAYS_SELECTION)
        state_by_value = dict(self._fields["state"]._description_selection(self.env))
        for line in self:
            day_name = weekday_by_number.get(line.day_number)
            day_name = _(day_name) if day_name else False
            interval = False
            if line.template_id:
                interval = "%s–%s" % (
                    line._format_float_hour(line.hour_from),
                    line._format_float_hour(line.hour_to),
                )
            parts = (
                line.employee_id.name,
                day_name,
                interval,
                line.work_location_id.name,
                line.template_id.name or state_by_value.get(line.state),
            )
            line.display_name = " · ".join(filter(None, parts)) or _("New")

    def _template_defaults(self, vals):
        values = dict(vals)
        if "template_id" not in values:
            return values
        template = self.env["hr.shift.template"].browse(values.get("template_id"))
        if template:
            values.setdefault("hour_from", template.start_time)
            values.setdefault("hour_to", template.end_time)
            if "work_location_id" not in values:
                employee = self.env["hr.employee"]
                if values.get("shift_id"):
                    employee = self.env["hr.shift.planning.shift"].browse(
                        values["shift_id"]
                    ).employee_id
                elif self:
                    employee = self[:1].employee_id
                location = (
                    template.default_work_location_id or employee.work_location_id
                )
                values["work_location_id"] = location.id
        elif values.get("template_id") is False:
            values.update(hour_from=0.0, hour_to=0.0, work_location_id=False)
        return values

    @api.onchange("template_id")
    def _onchange_template_work_location(self):
        if self.template_id:
            self.hour_from = self.template_id.start_time
            self.hour_to = self.template_id.end_time
            self.work_location_id = (
                self.template_id.default_work_location_id
                or self.employee_id.work_location_id
            )
        else:
            self.hour_from = self.hour_to = 0.0
            self.work_location_id = False

    def _is_shift_manager(self):
        return self.env.su or self.env.user.has_group("hr_shift.group_shift_manager")

    def _check_own_editor(self, shifts=None):
        if self._is_shift_manager() or self.env.context.get("shift_system_operation"):
            return
        if not self.env.user.has_group("hr_shift.group_shift_own_editor"):
            raise AccessError(_("You are not allowed to edit shift intervals."))
        checked_shifts = shifts if shifts is not None else self.shift_id
        if not checked_shifts:
            raise AccessError(_("A shift card is required to create an interval."))
        if any(shift.employee_id.user_id != self.env.user for shift in checked_shifts):
            raise AccessError(_("You can only edit your own shift intervals."))
        if any(
            shift.planning_id.state not in {"assignment", "planned"}
            for shift in checked_shifts
        ):
            raise AccessError(
                _("Shift intervals can only be edited during assignment or planning.")
            )

    def _reset_shift_review(self, shifts=None):
        shifts = shifts or self.shift_id
        lines = shifts.line_ids.filtered("reviewed")
        if lines:
            lines.with_context(shift_review_confirmation=True).write(
                {"reviewed": False}
            )

    @api.model_create_multi
    def create(self, vals_list):
        if any(
            not vals.get("shift_id") or vals.get("day_number") is None
            for vals in vals_list
        ):
            raise ValidationError(
                _("A shift card and day are required to create an interval.")
            )
        if self.env.context.get("controlled_interval_creation") and any(
            not vals.get("template_id") for vals in vals_list
        ):
            raise ValidationError(_("Select a shift template for the new interval."))
        prepared_vals = [self._template_defaults(vals) for vals in vals_list]
        shifts = self.env["hr.shift.planning.shift"].browse(
            [vals.get("shift_id") for vals in prepared_vals if vals.get("shift_id")]
        )
        self._check_own_editor(shifts)
        lines = super().create(prepared_vals)
        if not self.env.context.get("shift_review_confirmation"):
            lines._reset_shift_review()
        return lines

    def write(self, vals):
        self._check_own_editor()
        if vals.get("reviewed") and not (
            self._is_shift_manager()
            or self.env.context.get("shift_review_confirmation")
        ):
            raise AccessError(_("Only a Shift Manager can review a schedule."))
        if "shift_id" in vals:
            if not vals["shift_id"]:
                raise ValidationError(
                    _("A shift interval must belong to a shift card.")
                )
            self._check_own_editor(
                self.env["hr.shift.planning.shift"].browse(vals["shift_id"])
            )
        if (
            len(self) > 1
            and vals.get("template_id")
            and "work_location_id" not in vals
        ):
            template = self.env["hr.shift.template"].browse(vals["template_id"])
            lines_by_location = defaultdict(lambda: self.browse())
            for line in self:
                location = (
                    template.default_work_location_id
                    or line.employee_id.work_location_id
                )
                lines_by_location[location.id] |= line
            for location_id, lines in lines_by_location.items():
                lines.write(dict(vals, work_location_id=location_id))
            return True
        prepared_vals = self._template_defaults(vals)
        reset_review = bool(SIGNIFICANT_LINE_FIELDS.intersection(prepared_vals))
        shifts = self.shift_id
        result = super().write(prepared_vals)
        if reset_review and not self.env.context.get("shift_review_confirmation"):
            self._reset_shift_review(shifts)
        return result

    def unlink(self):
        self._check_own_editor()
        shifts = self.shift_id
        result = super().unlink()
        if not self.env.context.get("shift_review_confirmation"):
            self._reset_shift_review(shifts)
        return result

    @api.constrains(
        "shift_id", "template_id", "hour_from", "hour_to", "work_location_id"
    )
    def _check_interval_values(self, require_location=False):
        for line in self.filtered("template_id"):
            if not 0 <= line.hour_from < line.hour_to <= 24:
                raise ValidationError(
                    _(
                        "Shift hours must satisfy 0 <= From < To <= 24. "
                        "Intervals crossing midnight are not supported."
                    )
                )
            if require_location and not line.work_location_id:
                raise ValidationError(
                    _(
                        "A work location is required before the schedule can be "
                        "reviewed."
                    )
                )
            if (
                line.work_location_id
                and line.work_location_id.company_id != line.employee_id.company_id
            ):
                raise ValidationError(
                    _("The work location must belong to the employee company.")
                )

    @api.constrains(
        "shift_id", "day_number", "template_id", "hour_from", "hour_to"
    )
    def _check_interval_overlap(self):
        for line in self.filtered("template_id"):
            overlap = self.search_count(
                [
                    ("id", "!=", line.id),
                    ("shift_id", "=", line.shift_id.id),
                    ("day_number", "=", line.day_number),
                    ("template_id", "!=", False),
                    ("hour_from", "<", line.hour_to),
                    ("hour_to", ">", line.hour_from),
                ],
                limit=1,
            )
            if overlap:
                raise ValidationError(
                    _("Shift intervals on the same day cannot overlap.")
                )

    @api.depends(
        "planning_id.start_date",
        "day_number",
        "template_id",
        "template_id.tz",
        "employee_id.resource_calendar_id.tz",
        "hour_from",
        "hour_to",
    )
    def _compute_shift_time(self):
        for line in self:
            if not (
                line.planning_id.start_date
                and line.day_number is not False
                and line.template_id
                and 0 <= line.hour_from < line.hour_to <= 24
            ):
                line.start_time = False
                line.end_time = False
                continue
            shift_date = line.template_id._get_weekdate(
                line.planning_id.start_date, int(line.day_number)
            )
            timezone = pytz.timezone(
                line.template_id.tz
                or line.employee_id.resource_calendar_id.tz
                or self.env.user.tz
                or "UTC"
            )
            try:
                start_time = self._localize_float_hour(
                    timezone, shift_date, line.hour_from
                )
                end_time = self._localize_float_hour(
                    timezone, shift_date, line.hour_to
                )
            except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError) as error:
                raise ValidationError(
                    _(
                        "The shift interval is invalid because of a daylight-saving "
                        "transition."
                    )
                ) from error
            line.start_time = start_time.astimezone(pytz.UTC).replace(tzinfo=None)
            line.end_time = end_time.astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def _localize_float_hour(self, timezone, shift_date, float_hour):
        total_minutes = round(float_hour * 60)
        if total_minutes == 24 * 60:
            local_datetime = datetime.combine(
                shift_date + timedelta(days=1), time.min
            )
        else:
            local_datetime = datetime.combine(
                shift_date,
                time(hour=total_minutes // 60, minute=total_minutes % 60),
            )
        return timezone.localize(local_datetime, is_dst=None)

    @api.depends(
        "template_id",
        "shift_id.planning_id.start_date",
        "day_number",
        "employee_id",
        "hour_from",
        "hour_to",
    )
    def _compute_state(self):
        return super()._compute_state()

    def _is_on_leave(self):
        if self.start_time and self.end_time and self.employee_id.resource_id:
            return bool(
                self.env["resource.calendar.leaves"].sudo().search_count(
                    [
                        ("resource_id", "=", self.employee_id.resource_id.id),
                        ("date_from", "<", self.end_time),
                        ("date_to", ">", self.start_time),
                    ],
                    limit=1,
                )
            )
        return super()._is_on_leave()

    def action_add_interval(self):
        self.ensure_one()
        self._check_own_editor()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "hr_shift.shift_planning_line_action"
        )
        action.update(
            {
                "view_mode": "form",
                "views": [(False, "form")],
                "target": "new",
                "res_id": False,
                "context": {
                    "default_shift_id": self.shift_id.id,
                    "default_day_number": self.day_number,
                    "default_hour_from": self.hour_to,
                    "default_work_location_id": self.work_location_id.id,
                    "controlled_interval_creation": True,
                },
            }
        )
        return action

    def action_delete_interval(self):
        self.ensure_one()
        self.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}
