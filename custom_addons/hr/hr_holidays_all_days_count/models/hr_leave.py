# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    calendar_days_count = fields.Integer(
        string="Calendar Days",
        compute="_compute_calendar_days_count",
        help="Number of calendar days from the request start date to the request end date, inclusive.",
    )

    @api.depends("request_date_from", "request_date_to")
    def _compute_calendar_days_count(self):
        for leave in self:
            if leave.request_date_from and leave.request_date_to:
                leave.calendar_days_count = (
                    leave.request_date_to - leave.request_date_from
                ).days + 1
            elif leave.request_date_from:
                leave.calendar_days_count = 1
            else:
                leave.calendar_days_count = 0
