{
    "name": "Employee Education Details",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "summary": "Education status and study course for employees",
    "depends": ["hr"],
    "data": [
        "security/ir.model.access.csv",
        "data/education_course_data.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
