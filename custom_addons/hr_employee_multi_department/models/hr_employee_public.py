from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    department_ids = fields.Many2many(
        comodel_name='hr.department',
        relation='hr_employee_department_rel',
        column1='employee_id',
        column2='department_id',
        string='Departments',
        readonly=True,
    )
