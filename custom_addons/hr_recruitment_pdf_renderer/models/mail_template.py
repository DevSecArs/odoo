from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    offer_pdf_manual_enabled = fields.Boolean(string='Prepare documents manually')
    offer_pdf_company_id = fields.Many2one(
        'res.company', string='Documents company', default=lambda self: self.env.company,
    )
    offer_pdf_document_ids = fields.One2many(
        'mail.template.offer.pdf.document', 'template_id', string='Documents',
    )
    offer_pdf_document_count = fields.Integer(compute='_compute_offer_pdf_document_count')

    @api.depends('offer_pdf_document_ids')
    def _compute_offer_pdf_document_count(self):
        for template in self:
            template.offer_pdf_document_count = len(template.offer_pdf_document_ids)

    @api.constrains('offer_pdf_manual_enabled', 'model_id')
    def _check_offer_pdf_model(self):
        for template in self.filtered('offer_pdf_manual_enabled'):
            if template.model != 'hr.applicant':
                raise ValidationError(_(
                    'Manual PDF documents can only be configured on hr.applicant email templates.'
                ))

    def _offer_pdf_check_ready(self, applicant=None):
        self.ensure_one()
        if not self.offer_pdf_manual_enabled or self.model != 'hr.applicant':
            raise ValidationError(_('Select an enabled manual PDF document template for applicants.'))
        active_documents = self.offer_pdf_document_ids.filtered('active')
        if not active_documents:
            raise ValidationError(_('The email template has no active documents.'))
        if applicant and self.offer_pdf_company_id and applicant.company_id != self.offer_pdf_company_id:
            raise ValidationError(_('The applicant and PDF template belong to different companies.'))
        invalid = active_documents.filtered(
            lambda document: document.document_type == 'fillable_pdf' and (
                not document.pdf_file
                or document.validation_state != 'valid'
                or document.field_ids.filtered(lambda field: not field.active)
            )
        )
        if invalid:
            raise ValidationError(_('Fix the PDF field mapping before starting the document process.'))
