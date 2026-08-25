import base64
import hashlib

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from .offer_pdf_service import MAX_PDF_SIZE, inspect_pdf


class OfferPdfDocument(models.Model):
    _name = 'mail.template.offer.pdf.document'
    _description = 'Manual Offer PDF Document'
    _order = 'sequence, id'

    name = fields.Char(string='PDF document name', required=True, translate=True)
    template_id = fields.Many2one('mail.template', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    pdf_file = fields.Binary(string='Source PDF', required=True, attachment=True)
    pdf_filename = fields.Char(string='Source filename', required=True)
    pdf_mimetype = fields.Char(string='MIME type', default='application/pdf', required=True)
    pdf_checksum = fields.Char(string='PDF checksum', readonly=True, copy=False)
    field_ids = fields.One2many('mail.template.offer.pdf.field', 'document_id', string='PDF fields')
    field_count = fields.Integer(string='Detected fields', readonly=True, copy=False)
    last_checked = fields.Datetime(string='Last validation', readonly=True, copy=False)
    validation_state = fields.Selection([('draft', 'Not checked'), ('valid', 'Valid'), ('invalid', 'Invalid')], string='Validation status', default='draft', readonly=True, copy=False)
    validation_message = fields.Char(string='Validation message', readonly=True, copy=False)

    _sql_constraints = [
        ('offer_pdf_document_name_unique', 'unique(template_id, name)', 'PDF document names must be unique per template.'),
    ]

    @api.constrains('pdf_file', 'pdf_filename', 'pdf_mimetype')
    def _check_and_sync_pdf_file(self):
        for document in self:
            if document.pdf_file:
                if document.pdf_mimetype != 'application/pdf':
                    raise ValidationError(_('Only application/pdf files can be used as offer documents.'))
                document._sync_pdf_fields()

    def _sync_pdf_fields(self):
        self.ensure_one()
        try:
            raw_pdf = base64.b64decode(self.pdf_file, validate=True)
            if len(raw_pdf) > MAX_PDF_SIZE:
                raise ValidationError(_('The PDF exceeds the allowed size.'))
            discovered = inspect_pdf(raw_pdf)
        except (ValueError, TypeError, ValidationError) as error:
            self.with_context(offer_pdf_skip_validation=True).write({
                'validation_state': 'invalid',
                'validation_message': str(error),
                'last_checked': fields.Datetime.now(),
                'field_count': 0,
            })
            raise ValidationError(str(error))

        discovered_by_name = {field['name']: field for field in discovered}
        commands = []
        for field in self.field_ids:
            current = discovered_by_name.pop(field.pdf_field_name, None)
            if current:
                commands.append(Command.update(field.id, {'active': True, 'multiline': current['multiline'], 'label': field.label or current['label']}))
            else:
                commands.append(Command.update(field.id, {'active': False}))
        commands.extend(Command.create({
            'pdf_field_name': name,
            'label': values['label'],
            'multiline': values['multiline'],
            'sequence': 10,
        }) for name, values in discovered_by_name.items())
        self.with_context(offer_pdf_skip_validation=True).write({
            'field_ids': commands,
            'pdf_checksum': hashlib.sha256(raw_pdf).hexdigest(),
            'field_count': len(discovered),
            'validation_state': 'valid',
            'validation_message': False,
            'last_checked': fields.Datetime.now(),
        })

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        for document in documents:
            if document.pdf_file:
                document._sync_pdf_fields()
        return documents

    def write(self, values):
        result = super().write(values)
        if 'pdf_file' in values and not self.env.context.get('offer_pdf_skip_validation'):
            for document in self:
                document._sync_pdf_fields()
        return result

    def action_open_field_configuration(self):
        """Open the detected field mapping from the template PDF tab."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'hr_recruitment_pdf_offer.mail_template_offer_pdf_document_view_form'
            ).id,
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }
