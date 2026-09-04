from odoo import models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    def _compute_total_employee(self):
        employee_data = self.env['hr.employee'].sudo()._read_group(
            [
                ('department_ids', 'in', self.ids),
                ('company_id', 'in', self.env.companies.ids),
            ],
            ['department_ids'],
            ['__count'],
        )
        employee_count = {
            department.id: count for department, count in employee_data
        }
        for department in self:
            department.total_employee = employee_count.get(department.id, 0)

    def action_employee_from_department(self):
        action = super().action_employee_from_department()
        context = dict(action.get('context', {}))
        context.pop('searchpanel_default_department_id', None)
        context.pop('search_default_department_id', None)
        context.update({
            'searchpanel_default_department_ids': self.ids,
            'search_default_department_ids': self.id,
        })
        action['context'] = context
        return action
