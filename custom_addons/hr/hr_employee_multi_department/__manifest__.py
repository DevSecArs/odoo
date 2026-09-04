{
    'name': 'Мульти-отделы для сотрудников',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Assign employees to primary and additional departments',
    'description': 'Assign employees to primary and additional departments.',
    'depends': ['hr'],
    'data': [
        'views/hr_employee_views.xml',
        'views/hr_employee_public_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
