from odoo import Command, api, fields, models


class HrPdfDocumentDraft(models.Model):
    """Persist manually entered PDF values until the document is sent."""

    _name = 'hr.pdf.document.draft'
    _description = 'Saved PDF Document Values'
    _order = 'write_date desc, id desc'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade', index=True)
    template_id = fields.Many2one('mail.template', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user, ondelete='cascade', index=True,
    )
    document_ids = fields.One2many('hr.pdf.document.draft.document', 'draft_id')

    _sql_constraints = [
        (
            'hr_pdf_document_draft_unique_user_applicant_template',
            'unique(applicant_id, template_id, user_id)',
            'Only one saved PDF document draft is allowed per user, applicant and template.',
        ),
    ]

    @api.model
    def _get_current_draft(self, applicant, template):
        return self.search([
            ('applicant_id', '=', applicant.id),
            ('template_id', '=', template.id),
            ('user_id', '=', self.env.user.id),
        ], limit=1)

    @api.model
    def save_from_wizard(self, wizard):
        """Replace the saved snapshot with the values currently visible in a wizard."""
        wizard.ensure_one()
        draft = self._get_current_draft(wizard.applicant_id, wizard.template_id)
        if not draft:
            draft = self.create({
                'applicant_id': wizard.applicant_id.id,
                'template_id': wizard.template_id.id,
            })

        documents = []
        for document in wizard.document_ids:
            if not document.source_document_id:
                continue
            values = {
                'source_document_id': document.source_document_id.id,
                'document_type': document.document_type,
                'value_map': {
                    value.pdf_field_name: value.value or ''
                    for value in document.value_ids
                } if document.document_type == 'fillable_pdf' else {},
            }
            if document.document_type == 'requested_file' and document.uploaded_file:
                metadata = document._validate_upload()
                values.update({
                    'uploaded_file': document.uploaded_file,
                    'uploaded_filename': metadata['filename'],
                    'uploaded_mimetype': metadata['mimetype'],
                    'uploaded_checksum': metadata['checksum'],
                    'uploaded_size': metadata['size'],
                })
            documents.append(Command.create(values))
        draft.write({'document_ids': [Command.clear(), *documents]})
        return draft


class HrPdfDocumentDraftDocument(models.Model):
    _name = 'hr.pdf.document.draft.document'
    _description = 'Saved PDF Document Draft'

    draft_id = fields.Many2one('hr.pdf.document.draft', required=True, ondelete='cascade', index=True)
    source_document_id = fields.Many2one(
        'mail.template.offer.pdf.document', required=True, ondelete='cascade', index=True,
    )
    value_map = fields.Json(default=dict)
    document_type = fields.Selection(
        [('fillable_pdf', 'Fillable PDF'), ('requested_file', 'Requested file')],
        required=True,
        default='fillable_pdf',
    )
    uploaded_file = fields.Binary(string='Uploaded document', attachment=True)
    uploaded_filename = fields.Char(string='Uploaded filename')
    uploaded_mimetype = fields.Char(string='File format', readonly=True)
    uploaded_checksum = fields.Char(readonly=True)
    uploaded_size = fields.Integer(string='File size (bytes)', readonly=True)

    _sql_constraints = [
        (
            'hr_pdf_document_draft_document_unique_source',
            'unique(draft_id, source_document_id)',
            'A document can only be saved once in the same draft.',
        ),
    ]
