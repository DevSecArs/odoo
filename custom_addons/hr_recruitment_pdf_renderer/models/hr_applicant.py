from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    offer_pdf_activity_id = fields.Many2one('mail.activity', string='PDF document activity', copy=False, readonly=True)

    def _offer_pdf_check_user(self):
        if not self.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            raise AccessError(_('Only Recruitment users can prepare PDF documents.'))
        self.check_access('read')
        self.check_access_rule('read')

    def _offer_pdf_check_email(self):
        self.ensure_one()
        if not self.email_from and not (self.partner_id and self.partner_id.email):
            raise ValidationError(_('The applicant must have an email address before preparing a document.'))

    def action_open_offer_pdf_wizard(self):
        self.ensure_one()
        self._offer_pdf_check_user()
        self._offer_pdf_check_email()
        template = self.stage_id.offer_mail_template_id
        if not template:
            template = self.env['mail.template'].search([
                ('offer_pdf_manual_enabled', '=', True),
                ('model', '=', 'hr.applicant'),
                '|', ('offer_pdf_company_id', '=', False), ('offer_pdf_company_id', '=', self.company_id.id),
            ], order='id', limit=1)
        if not template:
            raise ValidationError(_('No enabled manual PDF document template is available for this applicant.'))
        template._offer_pdf_check_ready(self)
        wizard = self.env['hr.offer.pdf.send.wizard'].create({
            'applicant_id': self.id,
            'template_id': template.id,
        })
        return wizard.action_open()

    def write(self, values):
        stage_changed = 'stage_id' in values
        result = super().write(values)
        if stage_changed:
            for applicant in self:
                applicant._offer_pdf_schedule_stage_activity()
        return result

    def _track_template(self, changes):
        """Never let the ordinary stage mail path send an empty manual PDF."""
        templates = super()._track_template(changes)
        if 'stage_id' in changes:
            applicant = self[:1]
            if applicant.stage_id.template_id.offer_pdf_manual_enabled:
                templates.pop('stage_id', None)
        return templates

    def _offer_pdf_schedule_stage_activity(self):
        self.ensure_one()
        template = self.stage_id.offer_mail_template_id
        if not template:
            return
        # An invalid mapping must not block a normal kanban stage move. The activity
        # leads the HR user to the wizard, where readiness is checked before any data
        # is copied or email can be queued.
        if not template.offer_pdf_manual_enabled or template.model != 'hr.applicant':
            return
        if template.offer_pdf_company_id and template.offer_pdf_company_id != self.company_id:
            return
        activity_type = self.env.ref('hr_recruitment_pdf_renderer.mail_activity_type_offer_pdf')
        existing = self.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)
        if existing:
            self.offer_pdf_activity_id = existing[:1]
            return
        activity = self.activity_schedule(
            'hr_recruitment_pdf_renderer.mail_activity_type_offer_pdf',
            user_id=(self.user_id or self.env.user).id,
            summary=_('Prepare PDF documents'),
            note=_('Prepare the completed PDF documents before sending them to the candidate.'),
        )
        self.offer_pdf_activity_id = activity
