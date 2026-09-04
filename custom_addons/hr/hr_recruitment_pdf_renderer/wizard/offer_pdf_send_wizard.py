import base64
import math

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.pdf_form_core.services import inspect_pdf, render_pdf
from odoo.addons.hr_recruitment_pdf_renderer.models.offer_attachment_service import (
    DEFAULT_MAX_REQUESTED_FILE_SIZE,
    validate_requested_file,
)


def _attachment_filename(document):
    """Use the document name selected in the template without altering it."""
    return document.name or 'document.pdf'


class OfferPdfSendWizard(models.TransientModel):
    _name = 'hr.offer.pdf.send.wizard'
    _description = 'Send Recruitment Documents'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True, ondelete='cascade')
    # The template can be deleted; the remaining snapshot is retained only for safe cleanup.
    template_id = fields.Many2one('mail.template', readonly=True, ondelete='set null')
    draft_id = fields.Many2one('hr.pdf.document.draft', readonly=True, ondelete='set null')
    document_ids = fields.One2many('hr.offer.pdf.send.document', 'wizard_id', string='Documents', readonly=True)
    current_document_id = fields.Many2one('hr.offer.pdf.send.document', readonly=True, ondelete='set null')
    current_document_name = fields.Char(related='current_document_id.name', readonly=True)
    current_document_type = fields.Selection(related='current_document_id.document_type', readonly=True)
    current_upload_required = fields.Boolean(related='current_document_id.upload_required', readonly=True)
    current_uploaded_file = fields.Binary(related='current_document_id.uploaded_file', readonly=False)
    current_uploaded_filename = fields.Char(related='current_document_id.uploaded_filename', readonly=False)
    current_uploaded_mimetype = fields.Char(related='current_document_id.uploaded_mimetype', readonly=True)
    current_uploaded_size = fields.Integer(related='current_document_id.uploaded_size', readonly=True)
    current_value_ids = fields.One2many(related='current_document_id.value_ids', readonly=False)
    current_index = fields.Integer(default=0, readonly=True)
    document_count = fields.Integer(compute='_compute_document_count')
    step_label = fields.Char(compute='_compute_step_label')
    state = fields.Selection(
        [('draft', 'Draft'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')],
        default='draft',
        readonly=True,
    )
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
            wizard.step_label = _(
                '%(current)s of %(total)s',
                current=wizard.current_index + 1,
                total=wizard.document_count,
            )

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._check_access_and_configuration()
            wizard.draft_id = self.env['hr.pdf.document.draft']._get_current_draft(
                wizard.applicant_id, wizard.template_id,
            )
            wizard._copy_configuration()
        return wizards

    def write(self, values):
        """Write upload data and its filename to the step in one operation.

        Writable related fields are inversed separately by the ORM.  The web
        binary widget sends the binary value before its filename, which used
        to trigger attachment validation with an empty filename.
        """
        values = dict(values)
        upload_values = {}
        upload_field_map = {
            'current_uploaded_file': 'uploaded_file',
            'current_uploaded_filename': 'uploaded_filename',
        }
        for wizard_field, document_field in upload_field_map.items():
            if wizard_field in values:
                upload_values[document_field] = values.pop(wizard_field)
        result = super().write(values)
        if upload_values:
            for wizard in self:
                wizard.current_document_id.write(upload_values)
        return result

    def _check_access_and_configuration(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            raise AccessError(_('Only Recruitment users can prepare documents.'))
        self.applicant_id.check_access('read')
        if not self.template_id:
            raise ValidationError(_('The email template was deleted. Start a new PDF document process.'))
        self.template_id._offer_pdf_check_ready(self.applicant_id)
        self.applicant_id._offer_pdf_check_email()

    def _copy_configuration(self):
        self.ensure_one()
        if self.document_ids:
            return
        commands = []
        source_documents = self.template_id.offer_pdf_document_ids.filtered('active')
        source_documents = (
            source_documents.filtered(lambda document: document.document_type == 'fillable_pdf').sorted(
                key=lambda document: (document.sequence, document.id)
            )
            + source_documents.filtered(lambda document: document.document_type == 'requested_file').sorted(
                key=lambda document: (document.sequence, document.id)
            )
        )
        for step_sequence, document in enumerate(source_documents, start=1):
            document_values = {
                'source_document_id': document.id,
                'name': document.name,
                'sequence': document.sequence,
                'step_sequence': step_sequence,
                'document_type': document.document_type,
                'upload_required': document.upload_required,
            }
            if document.document_type == 'requested_file':
                commands.append(Command.create(document_values))
                continue
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
            document_values.update({
                'source_pdf': document.pdf_file,
                'source_filename': document.pdf_filename,
                # Always use the fields found in this exact PDF snapshot.  A
                # legacy or partly saved mapping must not omit a PDF field and
                # make previewing or sending impossible.
                'value_ids': value_commands,
            })
            commands.append(Command.create(document_values))
        self.write({'document_ids': commands})
        current = self._ordered_documents()[:1]
        if not current:
            raise ValidationError(_('The email template has no active document.'))
        self.write({'current_document_id': current.id, 'current_index': 0, 'preview_stale': True})
        self._apply_saved_draft()

    def _apply_saved_draft(self):
        """Restore values saved by the current user for this applicant and template."""
        self.ensure_one()
        if not self.draft_id:
            return
        saved_documents = {
            document.source_document_id.id: document
            for document in self.draft_id.document_ids
        }
        for document in self.document_ids:
            saved = saved_documents.get(document.source_document_id.id)
            if not saved:
                continue
            if document.document_type == 'requested_file':
                document.write({
                    'uploaded_file': saved.uploaded_file,
                    'uploaded_filename': saved.uploaded_filename,
                })
                continue
            values = saved.value_map or {}
            for value in document.value_ids:
                if value.pdf_field_name in values:
                    value.value = values[value.pdf_field_name]

    def _ordered_documents(self):
        self.ensure_one()
        return self.document_ids.sorted(key=lambda document: (document.step_sequence, document.id))

    def action_open(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'hr_recruitment_pdf_renderer.action_hr_offer_pdf_send_wizard'
        )
        action.update({'res_id': self.id, 'target': 'new'})
        return action

    def _check_draft(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_('These documents have already been sent.'))
        if self.state == 'sending':
            raise UserError(_('These documents are currently being sent.'))
        self._check_access_and_configuration()

    def _validate_current_document(self):
        self.ensure_one()
        if self.current_document_id.document_type == 'requested_file':
            self.current_document_id._validate_upload(required=True)
            return
        missing = self.current_document_id.value_ids.filtered(
            lambda value: value.required and not (value.value or '').strip()
        )
        if missing:
            raise ValidationError(_('Fill in required field(s): %(names)s.', names=', '.join(missing.mapped('label'))))

    def _render_document(self, wizard_document, readonly=False):
        self.ensure_one()
        if wizard_document.document_type != 'fillable_pdf':
            raise UserError(_('Preview is only available for fillable PDF documents.'))
        values = {value.pdf_field_name: value.value or '' for value in wizard_document.value_ids}
        return render_pdf(base64.b64decode(wizard_document.source_pdf), values, readonly=readonly)

    def action_refresh_preview(self):
        self._check_draft()
        if self.current_document_type != 'fillable_pdf':
            raise UserError(_('Preview is only available for fillable PDF documents.'))
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
        """Save entered values in a persistent draft without closing the wizard."""
        self._check_draft()
        self.draft_id = self.env['hr.pdf.document.draft'].save_from_wizard(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Document values were saved.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_previous(self):
        self._check_draft()
        if self.current_index <= 0:
            raise UserError(_('This is the first document.'))
        documents = self._ordered_documents()
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
        documents = self._ordered_documents()
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
        for document in self._ordered_documents():
            if document.document_type == 'requested_file':
                document._validate_upload(required=True)
            else:
                missing = document.value_ids.filtered(lambda value: value.required and not (value.value or '').strip())
                if missing:
                    raise ValidationError(_('Fill in all required PDF fields before sending.'))
        self.write({'state': 'sending'})
        attachments = self.env['ir.attachment']
        try:
            for document in self._ordered_documents():
                if document.document_type == 'requested_file':
                    if not document.uploaded_file:
                        continue
                    metadata = document._validate_upload(required=True)
                    attachment = self.env['ir.attachment'].create({
                        'name': metadata['filename'],
                        'datas': document.uploaded_file,
                        'mimetype': metadata['mimetype'],
                        'res_model': 'hr.applicant',
                        'res_id': self.applicant_id.id,
                    })
                    attachments |= attachment
                    continue
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
            if not mail_id:
                raise ValidationError(_('The document email could not be queued.'))
            mail = self.env['mail.mail'].browse(mail_id)
            self.write({
                'state': 'sent',
                'sent_mail_id': mail.id,
                'sent_message_id': mail.mail_message_id.id,
                'preview_pdf': False,
                'preview_filename': False,
                'preview_stale': False,
            })
            self.document_ids.filtered('uploaded_file').write({
                'uploaded_file': False,
                'uploaded_filename': False,
            })
            if self.applicant_id.offer_pdf_activity_id:
                self.applicant_id.offer_pdf_activity_id.action_feedback()
                self.applicant_id.offer_pdf_activity_id = False
            if self.draft_id:
                self.draft_id.unlink()
        except Exception:
            # The message did not reach the queue, therefore no technical PDF copy must be retained.
            attachments.unlink()
            self.write({'state': 'failed'})
            raise
        return {'type': 'ir.actions.act_window_close'}

    def unlink(self):
        # Transient cleanup clears attachment-backed preview and uploads.
        self.filtered('preview_pdf').write({'preview_pdf': False, 'preview_filename': False})
        self.mapped('document_ids').filtered('uploaded_file').write({
            'uploaded_file': False,
            'uploaded_filename': False,
        })
        return super().unlink()


class OfferPdfSendDocument(models.TransientModel):
    _name = 'hr.offer.pdf.send.document'
    _description = 'Recruitment Document to Send'
    _order = 'step_sequence, id'

    wizard_id = fields.Many2one('hr.offer.pdf.send.wizard', required=True, ondelete='cascade')
    # This is an informational link only: source_pdf and field values are the immutable wizard snapshot.
    source_document_id = fields.Many2one('mail.template.offer.pdf.document', readonly=True, ondelete='set null')
    name = fields.Char(required=True, readonly=True)
    sequence = fields.Integer(readonly=True)
    step_sequence = fields.Integer(readonly=True)
    document_type = fields.Selection(
        [('fillable_pdf', 'Fillable PDF'), ('requested_file', 'Requested file')],
        required=True,
        default='fillable_pdf',
        readonly=True,
    )
    upload_required = fields.Boolean(string='Required upload', default=True, readonly=True)
    source_pdf = fields.Binary(readonly=True)
    source_filename = fields.Char(readonly=True)
    value_ids = fields.One2many('hr.offer.pdf.send.value', 'document_id', readonly=True)
    uploaded_file = fields.Binary(string='Upload document', attachment=True)
    uploaded_filename = fields.Char(string='Uploaded filename')
    uploaded_mimetype = fields.Char(string='File format', readonly=True)
    uploaded_checksum = fields.Char(readonly=True)
    uploaded_size = fields.Integer(string='File size (bytes)', readonly=True)

    @api.constrains('document_type', 'source_pdf')
    def _check_source_pdf(self):
        for document in self:
            if document.document_type == 'fillable_pdf' and not document.source_pdf:
                raise ValidationError(_('A fillable PDF wizard step requires a source PDF.'))

    def _maximum_upload_size(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'hr_recruitment_pdf_renderer.max_requested_file_size_mb', '25'
        )
        try:
            megabytes = float(value)
        except (TypeError, ValueError):
            megabytes = 25
        if not math.isfinite(megabytes) or megabytes <= 0:
            return DEFAULT_MAX_REQUESTED_FILE_SIZE
        return int(megabytes * 1024 * 1024)

    def _validate_upload(self, required=False):
        self.ensure_one()
        if self.document_type != 'requested_file':
            raise ValidationError(_('Uploads are only accepted for requested-file steps.'))
        if not self.uploaded_file:
            if required and self.upload_required:
                raise ValidationError(_('The requested document is required: %(name)s.', name=self.name))
            return False
        try:
            raw_file = base64.b64decode(self.uploaded_file, validate=True)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('The uploaded document data is invalid.')) from error
        return validate_requested_file(
            raw_file,
            self.uploaded_filename,
            max_size=self._maximum_upload_size(),
        )

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        for document in documents.filtered('uploaded_file'):
            document._sync_upload_metadata()
        return documents

    def write(self, values):
        result = super().write(values)
        if {'uploaded_file', 'uploaded_filename'} & set(values) and not self.env.context.get('offer_upload_skip_sync'):
            for document in self:
                document._sync_upload_metadata()
        return result

    def _sync_upload_metadata(self):
        self.ensure_one()
        if not self.uploaded_file:
            return self.with_context(offer_upload_skip_sync=True).write({
                'uploaded_filename': False,
                'uploaded_mimetype': False,
                'uploaded_checksum': False,
                'uploaded_size': 0,
            })
        metadata = self._validate_upload()
        return self.with_context(offer_upload_skip_sync=True).write({
            'uploaded_filename': metadata['filename'],
            'uploaded_mimetype': metadata['mimetype'],
            'uploaded_checksum': metadata['checksum'],
            'uploaded_size': metadata['size'],
        })


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
            self.mapped('document_id.wizard_id').filtered(
                lambda wizard: wizard.state == 'draft'
            ).write({'preview_stale': True})
        return result
