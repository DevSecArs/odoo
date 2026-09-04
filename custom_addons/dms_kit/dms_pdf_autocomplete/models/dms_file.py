import base64
import hashlib

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.pdf_form_core.services import inspect_pdf


class DmsFile(models.Model):
    _inherit = 'dms.file'

    pdf_form_state = fields.Selection(
        [('not_checked', 'Not checked'), ('valid', 'Valid'), ('invalid', 'Invalid')],
        default='not_checked',
        readonly=True,
        copy=False,
    )
    pdf_form_message = fields.Char(readonly=True, copy=False)
    pdf_form_checksum = fields.Char(readonly=True, copy=False, index=True)
    pdf_form_checked_at = fields.Datetime(readonly=True, copy=False)
    pdf_form_field_ids = fields.One2many(
        'dms.pdf.form.field', 'file_id', string='PDF form fields', copy=False,
    )
    pdf_form_field_count = fields.Integer(
        compute='_compute_pdf_form_enabled', store=True,
    )
    pdf_form_enabled = fields.Boolean(
        compute='_compute_pdf_form_enabled', store=True,
    )

    @api.depends('pdf_form_state', 'pdf_form_field_ids.active')
    def _compute_pdf_form_enabled(self):
        for record in self:
            active_fields = record.pdf_form_field_ids.filtered('active')
            record.pdf_form_field_count = len(active_fields)
            record.pdf_form_enabled = record.pdf_form_state == 'valid' and bool(active_fields)

    @api.model
    def _pdf_max_source_size(self):
        size_mb = int(self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.max_source_pdf_size_mb', 10,
        ))
        return max(1, size_mb) * 1024 * 1024

    def _check_pdf_configuration_write(self):
        for record in self:
            record.check_access('read')
            if not record.permission_write:
                raise AccessError(_('You need write access to configure this DMS PDF.'))
            if record.locked_by and record.locked_by != self.env.user:
                raise AccessError(_('The DMS file is locked by another user.'))
        return True

    def _pdf_raw_content(self):
        self.ensure_one()
        self.check_access('read')
        if self.mimetype != 'application/pdf':
            raise ValidationError(_('Only application/pdf DMS files can be filled.'))
        try:
            return base64.b64decode(self.content or b'', validate=True)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('The DMS file content is not valid base64 data.')) from error

    def _sync_pdf_form(self, raw_pdf, discovered, checksum):
        self.ensure_one()
        self._check_pdf_configuration_write()
        remaining = {item['name']: item for item in discovered}
        commands = []
        for form_field in self.pdf_form_field_ids.with_context(active_test=False):
            current = remaining.pop(form_field.pdf_field_name, None)
            if current:
                commands.append(Command.update(form_field.id, {
                    'active': True,
                    'multiline': current['multiline'],
                    'label': form_field.label or current['label'],
                }))
            else:
                commands.append(Command.update(form_field.id, {'active': False}))
        commands.extend(
            Command.create({
                'pdf_field_name': name,
                'label': item['label'],
                'multiline': item['multiline'],
                'sequence': index * 10,
            })
            for index, (name, item) in enumerate(remaining.items(), start=1)
        )
        self.with_context(dms_pdf_skip_reset=True).write({
            'pdf_form_field_ids': commands,
            'pdf_form_state': 'valid',
            'pdf_form_message': False,
            'pdf_form_checksum': checksum,
            'pdf_form_checked_at': fields.Datetime.now(),
        })

    def action_dms_pdf_fill(self):
        if len(self) != 1:
            raise ValidationError(_('Select exactly one DMS PDF file.'))
        self.ensure_one()
        if not self.env.user.has_group('dms.group_dms_user'):
            raise AccessError(_('Only DMS users can fill PDF templates.'))
        raw_pdf = self._pdf_raw_content()
        checksum = hashlib.sha256(raw_pdf).hexdigest()
        try:
            discovered = inspect_pdf(raw_pdf, max_size=self._pdf_max_source_size())
        except ValidationError as error:
            if self.permission_write and (not self.locked_by or self.locked_by == self.env.user):
                self.with_context(dms_pdf_skip_reset=True).write({
                    'pdf_form_state': 'invalid',
                    'pdf_form_message': str(error),
                    'pdf_form_checksum': checksum,
                    'pdf_form_checked_at': fields.Datetime.now(),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Invalid PDF form'),
                        'message': str(error),
                        'type': 'danger',
                        'sticky': True,
                    },
                }
            raise
        can_write = self.permission_write and (
            not self.locked_by or self.locked_by == self.env.user
        )
        current_names = set(self.pdf_form_field_ids.filtered('active').mapped('pdf_field_name'))
        discovered_names = {item['name'] for item in discovered}
        synchronized = (
            self.pdf_form_state == 'valid'
            and self.pdf_form_checksum == checksum
            and current_names == discovered_names
        )
        if can_write:
            self._sync_pdf_form(raw_pdf, discovered, checksum)
        elif not synchronized:
            raise AccessError(_(
                'This PDF template must be synchronized by a user with write access to the DMS file.',
            ))
        wizard = self.env['dms.pdf.autocomplete.wizard'].create({
            'source_file_id': self.id,
            'source_file_checksum': checksum,
            'source_pdf': base64.b64encode(raw_pdf),
            'source_filename': self.name,
            'save_mapping_as_default': can_write,
        })
        return wizard.action_open()

    def action_dms_pdf_check(self):
        return self.action_dms_pdf_fill()

    def write(self, values):
        content_fields = {'content', 'content_binary', 'content_file', 'attachment_id'}
        values = dict(values)
        if content_fields & set(values) and not self.env.context.get('dms_pdf_skip_reset'):
            values.update({
                'pdf_form_state': 'not_checked',
                'pdf_form_message': False,
                'pdf_form_checksum': False,
                'pdf_form_checked_at': False,
            })
        return super().write(values)
