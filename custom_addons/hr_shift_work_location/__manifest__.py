# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Интервалы и локации в сменах сотрудников",
    "summary": "Plan reviewed shift intervals by work location",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Shifts",
    "author": "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "depends": ["hr_shift"],
    "data": [
        "security/hr_shift_work_location_security.xml",
        "security/ir.model.access.csv",
        "views/shift_template_views.xml",
        "views/shift_planning_views.xml",
        "wizards/shift_planning_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/hr_shift_work_location/static/src/scss/shift_work_location.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
