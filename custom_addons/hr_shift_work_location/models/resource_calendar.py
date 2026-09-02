# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _attendance_intervals_batch(
        self, start_dt, end_dt, resources=None, domain=None, tz=None, lunch=False
    ):
        """Keep all shift intervals ordered after the upstream substitution."""
        result = super()._attendance_intervals_batch(
            start_dt, end_dt, resources, domain, tz, lunch
        )
        if resources and not lunch:
            for resource in resources:
                intervals = result.get(resource.id)
                if intervals:
                    intervals._items.sort(key=lambda item: (item[0], item[1]))
        return result
