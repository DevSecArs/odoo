from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from ..hooks import post_init_hook


@tagged('post_install', '-at_install')
class TestHrEmployeeMultiDepartment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Multi Department Company',
        })
        cls.other_company = cls.env['res.company'].create({
            'name': 'Other Multi Department Company',
        })
        cls.primary_department = cls.env['hr.department'].create({
            'name': 'Professional Internship',
            'company_id': cls.company.id,
        })
        cls.it_department = cls.env['hr.department'].create({
            'name': 'IT',
            'company_id': cls.company.id,
        })
        cls.other_department = cls.env['hr.department'].create({
            'name': 'Other Company Department',
            'company_id': cls.other_company.id,
        })
        cls.public_user = new_test_user(
            cls.env,
            login='multi.department.public.user',
            groups='base.group_user',
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    def _create_employee(self, name='Employee', **values):
        values.update({
            'name': name,
            'company_id': values.get('company_id', self.company.id),
        })
        return self.env['hr.employee'].create(values)

    def _assert_departments(self, employee, departments):
        self.assertEqual(set(employee.department_ids.ids), set(departments.ids))

    def test_create_adds_primary_department(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
        )

        self.assertEqual(employee.department_ids, self.primary_department)

    def test_employee_can_belong_to_multiple_departments(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )

        self._assert_departments(
            employee, self.primary_department | self.it_department
        )

    def test_search_by_additional_department(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )

        result = self.env['hr.employee'].search([
            ('department_ids', 'in', self.it_department.id),
        ])

        self.assertIn(employee, result)

    def test_changing_primary_keeps_previous_membership(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
        )

        employee.department_id = self.it_department

        self._assert_departments(
            employee, self.primary_department | self.it_department
        )

    def test_primary_department_cannot_be_removed_from_memberships(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )

        employee.department_ids = [Command.unlink(self.primary_department.id)]

        self.assertIn(self.primary_department, employee.department_ids)
        self.assertIn(self.it_department, employee.department_ids)

    def test_clearing_primary_keeps_other_memberships(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )

        employee.department_id = False

        self.assertFalse(employee.department_id)
        self._assert_departments(
            employee, self.primary_department | self.it_department
        )

    def test_department_from_another_company_is_rejected(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
        )

        with self.assertRaises(UserError):
            employee.department_ids = [Command.link(self.other_department.id)]

    def test_public_employee_departments_are_readable_and_searchable(self):
        employee = self._create_employee(
            name='Public Multi Department Employee',
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )
        public_employees = self.env['hr.employee.public'].with_user(
            self.public_user
        ).with_context(allowed_company_ids=self.company.ids)
        public_employee = public_employees.browse(employee.id)

        self._assert_departments(
            public_employee, self.primary_department | self.it_department
        )
        self.assertIn(
            public_employee,
            public_employees.search([
                ('department_ids', 'in', self.it_department.id),
            ]),
        )

    def test_department_counts_primary_and_additional_members_once(self):
        self._create_employee(
            department_id=self.primary_department.id,
            department_ids=[Command.link(self.it_department.id)],
        )
        second_employee = self._create_employee(
            name='Second Employee',
            department_id=self.it_department.id,
        )
        second_employee.department_ids = [Command.link(self.it_department.id)]

        departments = self.primary_department | self.it_department
        departments._compute_total_employee()

        self.assertEqual(self.primary_department.total_employee, 1)
        self.assertEqual(self.it_department.total_employee, 2)

    def test_department_employee_action_uses_membership_filter(self):
        action = self.it_department.action_employee_from_department()

        self.assertNotIn('searchpanel_default_department_id', action['context'])
        self.assertNotIn('search_default_department_id', action['context'])
        self.assertEqual(
            action['context']['searchpanel_default_department_ids'],
            self.it_department.ids,
        )
        self.assertEqual(
            action['context']['search_default_department_ids'],
            self.it_department.id,
        )
        self.assertEqual(
            action['context']['default_department_id'],
            self.it_department.id,
        )

    def test_additional_department_does_not_change_manager(self):
        primary_manager = self._create_employee(name='Primary Manager')
        it_manager = self._create_employee(name='IT Manager')
        self.primary_department.manager_id = primary_manager
        self.it_department.manager_id = it_manager
        employee = self._create_employee(
            department_id=self.primary_department.id,
        )

        self.assertEqual(employee.parent_id, primary_manager)
        employee.department_ids = [Command.link(self.it_department.id)]
        self.assertEqual(employee.parent_id, primary_manager)

        employee.department_id = self.it_department
        self.assertEqual(employee.parent_id, it_manager)

    def test_post_init_hook_is_idempotent(self):
        employee = self._create_employee(
            department_id=self.primary_department.id,
        )
        self.env.flush_all()
        self.env.cr.execute(
            'DELETE FROM hr_employee_department_rel WHERE employee_id = %s',
            [employee.id],
        )

        post_init_hook(self.env)
        post_init_hook(self.env)
        self.env.cr.execute(
            'SELECT COUNT(*) FROM hr_employee_department_rel '
            'WHERE employee_id = %s AND department_id = %s',
            [employee.id, self.primary_department.id],
        )

        self.assertEqual(self.env.cr.fetchone()[0], 1)

    def test_batch_primary_department_write_synchronizes_all_employees(self):
        employees = self.env['hr.employee'].create([
            {
                'name': 'Batch Employee One',
                'company_id': self.company.id,
                'department_id': self.primary_department.id,
            },
            {
                'name': 'Batch Employee Two',
                'company_id': self.company.id,
                'department_id': self.primary_department.id,
            },
        ])

        employees.write({'department_id': self.it_department.id})

        for employee in employees:
            self._assert_departments(
                employee, self.primary_department | self.it_department
            )
