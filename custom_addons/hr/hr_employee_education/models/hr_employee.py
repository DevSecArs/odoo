from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    education_status = fields.Selection([
        ("studying", "Studying"),
        ("graduated", "Graduated"),
    ], string="Education Status")
    education_course_id = fields.Many2one(
        "hr.employee.education.course",
        string="Study Course",
        ondelete="restrict",
    )

    @api.onchange("certificate", "education_status")
    def _onchange_education_course(self):
        for employee in self:
            if (
                employee.education_status != "studying"
                or not employee.certificate
                or employee.certificate not in {"bachelor", "specialist", "master"}
                or (
                    employee.education_course_id
                    and employee.education_course_id.degree != employee.certificate
                )
            ):
                employee.education_course_id = False

    @api.constrains("certificate", "education_status", "education_course_id")
    def _check_education_course(self):
        for employee in self:
            if employee.education_status != "studying" and employee.education_course_id:
                raise ValidationError(
                    "У сотрудника, который закончил обучение, курс обучения должен быть пустым."
                )
            if employee.education_course_id and (
                employee.certificate != employee.education_course_id.degree
            ):
                raise ValidationError(
                    "Курс обучения не соответствует степени диплома сотрудника."
                )
