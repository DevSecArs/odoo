from odoo import fields, models


class HrEmployeeEducationCourse(models.Model):
    _name = "hr.employee.education.course"
    _description = "Employee Education Course"
    _order = "degree, sequence, id"

    name = fields.Char(string="Course", required=True, translate=True)
    degree = fields.Selection([
        ("bachelor", "Bachelor"),
        ("specialist", "Specialist"),
        ("master", "Master"),
    ], string="Certificate Level", required=True, index=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "education_course_unique",
            "unique (degree, name)",
            "The course must be unique for each certificate level.",
        ),
    ]
