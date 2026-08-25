import base64

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.hr_recruitment_pdf_offer.models.offer_pdf_service import inspect_pdf, render_pdf


def _attachment_filename(document):
    """Use the document name selected in the template without altering it."""
    return document.name or 'document.pdf'


class OfferPdfSendWizard(models.TransientModel):
    _name = 'hr.offer.pdf.send.wizard'
    _description = 'Send PDF Documents'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True, ondelete='cascade')
    # The template can be deleted; the remaining snapshot is retained only for safe cleanup.
    template_id = fields.Many2one('mail.template', readonly=True, ondelete='set null')
    document_ids = fields.One2many('hr.offer.pdf.send.document', 'wizard_id', string='Documents', readonly=True)
    current_document_id = fields.Many2one('hr.offer.pdf.send.document', readonly=True, ondelete='set null')
    current_document_name = fields.Char(related='current_document_id.name', readonly=True)
    current_value_ids = fields.One2many(related='current_document_id.value_ids', readonly=False)
    current_index = fields.Integer(default=0, readonly=True)
    document_count = fields.Integer(compute='_compute_document_count')
    step_label = fields.Char(compute='_compute_step_label')
    state = fields.Selection([('draft', 'Draft'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')], default='draft', readonly=True)
    preview_stale = fields.Boolean(default=True, readonly=True)
    preview_pdf = fields.Binary(attachment=True, readonly=True)
    preview_filename = fields.Char(readonly=True)
    sent_mail_id = fields.Many2one('mail.mail', readonly=True, copy=False)
    sent_message_id = fields.Many2one('mail.message', readonly=True, copy=False)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for wizard in self:
            wizard.document_count = len(wizard.document_ids)

    @api.depends('current_index', 'document_count')
    def _compute_step_label(self):
        for wizard in self:
            wizard.step_label = _('%(current)s of %(total)s', current=wizard.current_index + 1, total=wizard.document_count)

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._check_access_and_configuration()
            wizard._copy_configuration()
        return wizards

    def _check_access_and_configuration(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            raise AccessError(_('Only Recruitment users can prepare PDF documents.'))
        self.applicant_id.check_access('read')
        self.applicant_id.check_access_rule('read')
        if not self.template_id:
            raise ValidationError(_('The email template was deleted. Start a new PDF document process.'))
        self.template_id._offer_pdf_check_ready(self.applicant_id)
        self.applicant_id._offer_pdf_check_email()

    def _copy_configuration(self):
        self.ensure_one()
        if self.document_ids:
            return
        commands = []
        for document in self.template_id.offer_pdf_document_ids.filtered('active').sorted('sequence'):
            source_pdf = base64.b64decode(document.pdf_file)
            configured_fields = {
                field.pdf_field_name: field
                for field in document.field_ids.filtered('active')
            }
            fallback_sequence = max(
                document.field_ids.filtered('active').mapped('sequence'), default=0
            )
            value_commands = []
            for index, discovered in enumerate(inspect_pdf(source_pdf), start=1):
                field = configured_fields.get(discovered['name'])
                value_commands.append(Command.create({
                    'source_field_id': field.id if field else False,
                    'pdf_field_name': discovered['name'],
                    'label': field.label if field else discovered['label'],
                    'sequence': field.sequence if field else fallback_sequence + index,
                    'required': field.required if field else False,
                    'multiline': discovered['multiline'],
                    'value': field._get_default_value(self.applicant_id) if field else '',
                }))
            commands.append(Command.create({
                'source_document_id': document.id,
                'name': document.name,
                'sequence': document.sequence,
                'source_pdf': document.pdf_file,
                'source_filename': document.pdf_filename,
                # Always use the fields found in this exact PDF snapshot.  A
                # legacy or partly saved mapping must not omit a PDF field and
                # make previewing or sending impossible.
                'value_ids': value_commands,
            }))
        self.write({'document_ids': commands})
        current = self.document_ids.sorted('sequence')[:1]
        if not current:
            raise ValidationError(_('The email template has no active PDF document.'))
        self.write({'current_document_id': current.id, 'current_index': 0, 'preview_stale': True})

    def action_open(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'hr_recruitment_pdf_offer.action_hr_offer_pdf_send_wizard'
        )
        action.update({'res_id': self.id, 'target': 'new'})
        return action

    def _check_draft(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_('These PDF documents have already been sent.'))
        if self.state == 'sending':
            raise UserError(_('These PDF documents are currently being sent.'))
        self._check_access_and_configuration()

    def _validate_current_document(self):
        self.ensure_one()
        missing = self.current_document_id.value_ids.filtered(lambda value: value.required and not (value.value or '').strip())
        if missing:
            raise ValidationError(_('Fill in required field(s): %(names)s.', names=', '.join(missing.mapped('label'))))

    def _render_document(self, wizard_document, readonly=False):
        self.ensure_one()
        values = {value.pdf_field_name: value.value or '' for value in wizard_document.value_ids}
        return render_pdf(base64.b64decode(wizard_document.source_pdf), values, readonly=readonly)

    def action_refresh_preview(self):
        self._check_draft()
        self._validate_current_document()
        try:
            preview = self._render_document(self.current_document_id)
        except ValidationError:
            self.write({'state': 'failed', 'preview_stale': True})
            raise
        self.write({
            'preview_pdf': base64.b64encode(preview),
            'preview_filename': _attachment_filename(self.current_document_id),
            'preview_stale': False,
            'state': 'draft',
        })
        return self.action_open()

    def action_save(self):
        """Persist editable transient values without closing the document wizard."""
        self._check_draft()
        return self.action_open()

    def action_previous(self):
        self._check_draft()
        if self.current_index <= 0:
            raise UserError(_('This is the first document.'))
        documents = self.document_ids.sorted('sequence')
        previous_index = self.current_index - 1
        self.write({
            'current_index': previous_index,
            'current_document_id': documents[previous_index].id,
            'preview_pdf': False,
            'preview_filename': False,
            'preview_stale': True,
        })
        return self.action_open()

    def action_next(self):
        self._check_draft()
        self._validate_current_document()
        documents = self.document_ids.sorted('sequence')
        if self.current_index >= len(documents) - 1:
            raise UserError(_('This is the last document. Use Send to deliver the documents.'))
        next_index = self.current_index + 1
        self.write({
            'current_index': next_index,
            'current_document_id': documents[next_index].id,
            'preview_pdf': False,
            'preview_filename': False,
            'preview_stale': True,
        })
        return self.action_open()

    def action_done(self):
        self.ensure_one()
        # A row lock makes the persisted state the idempotency authority, not the UI button.
        self.env.cr.execute('SELECT id FROM hr_offer_pdf_send_wizard WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.state == 'sent' and self.sent_mail_id:
            return {'type': 'ir.actions.act_window_close'}
        self._check_draft()
        for document in self.document_ids.sorted('sequence'):
            missing = document.value_ids.filtered(lambda value: value.required and not (value.value or '').strip())
            if missing:
                raise ValidationError(_('Fill in all required PDF fields before sending.'))
        self.write({'state': 'sending'})
        attachments = self.env['ir.attachment']
        try:
            for document in self.document_ids.sorted('sequence'):
                final_pdf = self._render_document(document, readonly=True)
                attachment = self.env['ir.attachment'].create({
                    'name': _attachment_filename(document),
                    'datas': base64.b64encode(final_pdf),
                    'mimetype': 'application/pdf',
                    'res_model': 'hr.applicant',
                    'res_id': self.applicant_id.id,
                })
                attachments |= attachment
            recipient = self.applicant_id.partner_id
            email_values = {'attachment_ids': [Command.link(attachment_id) for attachment_id in attachments.ids]}
            if recipient:
                email_values['recipient_ids'] = [Command.link(recipient.id)]
            else:
                email_values['email_to'] = self.applicant_id.email_from
            mail_id = self.template_id.send_mail(
                self.applicant_id.id,
                force_send=False,
                raise_exception=True,
                email_values=email_values,
            )
            mail = self.env['mail.mail'].browse(mail_id)
            self.write({
                'state': 'sent',
                'sent_mail_id': mail.id,
                'sent_message_id': mail.mail_message_id.id,
                'preview_pdf': False,
                'preview_filename': False,
                'preview_stale': False,
            })
            if self.applicant_id.offer_pdf_activity_id:
                self.applicant_id.offer_pdf_activity_id.action_feedback()
                self.applicant_id.offer_pdf_activity_id = False
        except Exception:
            # The message did not reach the queue, therefore no technical PDF copy must be retained.
            attachments.unlink()
            self.write({'state': 'failed'})
            raise
        return {'type': 'ir.actions.act_window_close'}

    def unlink(self):
        # Transient record cleanup also clears its attachment-backed preview.
        self.filtered('preview_pdf').write({'preview_pdf': False, 'preview_filename': False})
        return super().unlink()


class OfferPdfSendDocument(models.TransientModel):
    _name = 'hr.offer.pdf.send.document'
    _description = 'PDF Document to Send'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('hr.offer.pdf.send.wizard', required=True, ondelete='cascade')
    # This is an informational link only: source_pdf and field values are the immutable wizard snapshot.
    source_document_id = fields.Many2one('mail.template.offer.pdf.document', readonly=True, ondelete='set null')
    name = fields.Char(required=True, readonly=True)
    sequence = fields.Integer(readonly=True)
    source_pdf = fields.Binary(required=True, readonly=True)
    source_filename = fields.Char(readonly=True)
    value_ids = fields.One2many('hr.offer.pdf.send.value', 'document_id', readonly=True)


class OfferPdfSendValue(models.TransientModel):
    _name = 'hr.offer.pdf.send.value'
    _description = 'PDF Document Field Value'
    _order = 'sequence, id'

    document_id = fields.Many2one('hr.offer.pdf.send.document', required=True, ondelete='cascade')
    # Keep a running wizard usable if the HR manager removes the old mapping.
    source_field_id = fields.Many2one('mail.template.offer.pdf.field', readonly=True, ondelete='set null')
    pdf_field_name = fields.Char(required=True, readonly=True)
    label = fields.Char(string='Field', required=True, readonly=True)
    sequence = fields.Integer(string='Sequence', readonly=True)
    required = fields.Boolean(string='Required', readonly=True)
    multiline = fields.Boolean(string='Multiline', readonly=True)
    value = fields.Text(string='Value')

    def write(self, values):
        result = super().write(values)
        if 'value' in values:
            self.mapped('document_id.wizard_id').filtered(lambda wizard: wizard.state == 'draft').write({'preview_stale': True})
        return result
