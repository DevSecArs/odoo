# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    """Backfill new factual fields without replacing later manual values."""
    if not isinstance(env, api.Environment):
        env = api.Environment(env, SUPERUSER_ID, {})
    lines = env["hr.shift.planning.line"].sudo().search(
        [("template_id", "!=", False)]
    )
    for template in lines.template_id:
        missing_hours = lines.filtered(
            lambda line, current=template: line.template_id == current
            and not line.hour_from
            and not line.hour_to
        )
        if missing_hours:
            missing_hours.with_context(
                shift_system_operation=True,
                shift_review_confirmation=True,
            ).write(
                {"hour_from": template.start_time, "hour_to": template.end_time}
            )
    missing_location = lines.filtered(
        lambda line: not line.work_location_id and line.employee_id.work_location_id
    )
    for location in missing_location.employee_id.work_location_id:
        location_lines = missing_location.filtered(
            lambda line, current=location: line.employee_id.work_location_id == current
        )
        location_lines.with_context(
            shift_system_operation=True,
            shift_review_confirmation=True,
        ).write(
            {"work_location_id": location.id}
        )
    lines.filtered(
        lambda line: not line.work_location_id and line.reviewed
    ).with_context(shift_review_confirmation=True).write({"reviewed": False})
