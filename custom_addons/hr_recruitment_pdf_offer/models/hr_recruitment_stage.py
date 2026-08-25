from odoo import fields, models


class HrRecruitmentStage(models.Model):
    _inherit = 'hr.recruitment.stage'

    offer_mail_template_id = fields.Many2one(
        'mail.template',
        string='Manual PDF offer template',
        domain="[('model', '=', 'hr.applicant'), ('offer_pdf_manual_enabled', '=', True)]",
        check_company=False,
        groups='hr_recruitment.group_hr_recruitment_manager',
    )
