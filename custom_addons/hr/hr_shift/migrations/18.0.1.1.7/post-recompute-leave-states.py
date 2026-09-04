# Copyright 2026 DevSecArs
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Recompute existing lines now that leave checks do not require a shift."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["hr.shift.planning.line"].search([])._compute_state()
