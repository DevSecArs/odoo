# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class RecruitmentDegree(models.Model):
    _name = "hr.recruitment.degree"
    _description = "Applicant Degree"

    name = fields.Char("Degree Name", required=True, translate=True)
    sequence = fields.Integer("Sequence", default=1)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the Degree of Recruitment must be unique!')
    ]

    @api.model
    def _ensure_default_degrees(self):
        """Ensure the standard recruitment degree list includes Russian degrees."""
        degrees = {
            'Graduate': 1,
            'Certificate': 2,
            'Bachelor Degree': 3,
            'Specialist': 4,
            'Master Degree': 5,
            'Candidate of Sciences': 6,
            'Doctoral Degree': 7,
        }
        degrees_model = self.with_context(lang='en_US')
        for name, sequence in degrees.items():
            degree = degrees_model.search([('name', '=', name)], limit=1)
            if degree:
                degree.sequence = sequence
            else:
                degrees_model.create({'name': name, 'sequence': sequence})
