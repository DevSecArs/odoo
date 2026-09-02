from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Command


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    department_ids = fields.Many2many(
        comodel_name='hr.department',
        relation='hr_employee_department_rel',
        column1='employee_id',
        column2='department_id',
        string='Departments',
        check_company=True,
        tracking=True,
        help=(
            'All departments the employee belongs to. The primary department '
            'is added automatically and cannot be removed from this list while '
            'it remains the primary department.'
        ),
    )

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_primary_department()
        employees._check_company(['department_ids'])
        return employees

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_primary_department_sync'):
            self._sync_primary_department()
        if 'company_id' in vals or 'department_ids' in vals or 'department_id' in vals:
            self._check_company(['department_ids'])
        return result

    def _sync_primary_department(self):
        """Ensure each primary department is also a full membership."""
        if self.env.context.get('skip_primary_department_sync'):
            return

        employees_by_department = defaultdict(lambda: self.env['hr.employee'])
        for employee in self:
            if (
                employee.department_id
                and employee.department_id not in employee.department_ids
            ):
                employees_by_department[employee.department_id.id] |= employee

        for department_id, employees in employees_by_department.items():
            employees.with_context(skip_primary_department_sync=True).write({
                'department_ids': [Command.link(department_id)],
            })
