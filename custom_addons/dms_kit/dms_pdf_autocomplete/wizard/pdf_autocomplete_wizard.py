import base64
import hashlib
import io
import re
import secrets
import unicodedata
import zipfile

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.pdf_form_core.services import inspect_pdf, render_pdf


FILENAME_UNSAFE_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]+')
TARGET_MODEL_NAMES = {'employee': 'hr.employee', 'partner': 'res.partner'}


def safe_pdf_filename(source_name, recipient_name, record_id):
    stem = (source_name or 'document').rsplit('.', 1)[0]
    text = unicodedata.normalize('NFC', f'{stem} - {recipient_name}')
    text = FILENAME_UNSAFE_RE.sub('_', text).strip(' ._')
    suffix = f' - {record_id}'
    prefix = text[:max(1, 180 - len(suffix))].rstrip(' ._') or 'document'
    return f'{prefix}{suffix}.pdf'


class DmsPdfAutocompleteWizard(models.TransientModel):
    _name = 'dms.pdf.autocomplete.wizard'
    _description = 'DMS PDF Autocomplete Wizard'

    owner_user_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, readonly=True,
    )
    source_file_id = fields.Many2one('dms.file', required=True, readonly=True, ondelete='cascade')
    source_file_checksum = fields.Char(required=True, readonly=True)
    source_pdf = fields.Binary(required=True, readonly=True, attachment=True)
    source_filename = fields.Char(required=True, readonly=True)
    target_model = fields.Selection(
        [('employee', 'Employees'), ('partner', 'Contacts')],
        default='employee',
        required=True,
    )
    target_res_model = fields.Char(compute='_compute_target_res_model')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    partner_ids = fields.Many2many('res.partner', string='Contacts')
    mapping_ids = fields.One2many('dms.pdf.autocomplete.mapping', 'wizard_id')
    recipient_ids = fields.One2many('dms.pdf.autocomplete.recipient', 'wizard_id')
    current_recipient_id = fields.Many2one('dms.pdf.autocomplete.recipient', ondelete='set null')
    current_manual_value_ids = fields.One2many(
        related='current_recipient_id.manual_value_ids', readonly=False,
    )
    current_automatic_value_ids = fields.One2many(
        related='current_recipient_id.automatic_value_ids', readonly=True,
    )
    current_preview_pdf = fields.Binary(related='current_recipient_id.preview_pdf', readonly=True)
    current_preview_filename = fields.Char(related='current_recipient_id.preview_filename', readonly=True)
    current_preview_stale = fields.Boolean(related='current_recipient_id.preview_stale', readonly=True)
    current_index = fields.Integer(default=0, readonly=True)
    recipient_count = fields.Integer(compute='_compute_recipient_count')
    step_label = fields.Char(compute='_compute_recipient_count')
    retention_days = fields.Integer(default=0)
    save_mapping_as_default = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ('select_recipients', 'Select recipients'),
            ('map_fields', 'Map fields'),
            ('enter_values', 'Enter values'),
            ('review', 'Review'),
            ('generating', 'Generating'),
            ('ready', 'Ready'),
            ('sending', 'Sending'),
            ('done', 'Done'),
            ('failed', 'Failed'),
        ],
        default='select_recipients',
        required=True,
        readonly=True,
    )
    download_token = fields.Char(readonly=True, copy=False)
    download_token_expires_at = fields.Datetime(readonly=True, copy=False)
    download_token_used = fields.Boolean(readonly=True, copy=False)
    batch_id = fields.Many2one('dms.pdf.generation.batch', readonly=True, ondelete='set null')

    @api.depends('target_model')
    def _compute_target_res_model(self):
        for wizard in self:
            wizard.target_res_model = TARGET_MODEL_NAMES.get(wizard.target_model)

    @api.depends('recipient_ids', 'current_index')
    def _compute_recipient_count(self):
        for wizard in self:
            wizard.recipient_count = len(wizard.recipient_ids)
            wizard.step_label = _(
                '%(current)s of %(total)s',
                current=min(wizard.current_index + 1, len(wizard.recipient_ids)),
                total=len(wizard.recipient_ids),
            )

    @api.constrains('retention_days')
    def _check_retention_days(self):
        if any(wizard.retention_days < 0 for wizard in self):
            raise ValidationError(_('Retention days cannot be negative.'))

    @api.onchange('target_model')
    def _onchange_target_model(self):
        if self.target_model == 'employee':
            self.partner_ids = [Command.clear()]
        else:
            self.employee_ids = [Command.clear()]

    def _check_owner(self):
        self.ensure_one()
        if self.owner_user_id != self.env.user:
            raise AccessError(_('You cannot access another user’s PDF wizard.'))
        self.source_file_id.check_access('read')
        return True

    @api.model
    def _max_batch_size(self):
        return max(1, int(self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.max_batch_size', 100,
        )))

    def _selected_records(self):
        self.ensure_one()
        records = self.employee_ids if self.target_model == 'employee' else self.partner_ids
        model = self.env[TARGET_MODEL_NAMES[self.target_model]]
        model.check_access('read')
        records.check_access('read')
        if not records:
            raise ValidationError(_('Select at least one recipient.'))
        if len(records) > self._max_batch_size():
            raise ValidationError(_('The selected batch exceeds the configured recipient limit.'))
        return records

    def action_open(self):
        self._check_owner()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'dms_pdf_autocomplete.action_pdf_autocomplete_wizard'
        )
        action.update({'res_id': self.id, 'target': 'new'})
        return action

    def action_prepare_mappings(self):
        self._check_owner()
        self._selected_records()
        raw_pdf = base64.b64decode(self.source_pdf)
        discovered = inspect_pdf(raw_pdf, max_size=self.source_file_id._pdf_max_source_size())
        active_fields = {
            item.pdf_field_name: item
            for item in self.source_file_id.pdf_form_field_ids.filtered('active')
        }
        if set(active_fields) != {item['name'] for item in discovered}:
            raise ValidationError(_('The PDF field configuration is no longer synchronized.'))
        saved = {
            mapping.form_field_id.id: mapping
            for mapping in self.env['dms.pdf.field.mapping'].search([
                ('form_field_id', 'in', [item.id for item in active_fields.values()]),
                ('target_model', '=', self.target_model),
                ('active', '=', True),
            ])
        }
        self.mapping_ids = [Command.clear()] + [
            Command.create({
                'form_field_id': form_field.id,
                'pdf_field_name': form_field.pdf_field_name,
                'label': form_field.label,
                'multiline': form_field.multiline,
                'fill_mode': saved.get(form_field.id).fill_mode if saved.get(form_field.id) else 'manual',
                'source_field_path': saved.get(form_field.id).source_field_path if saved.get(form_field.id) else False,
            })
            for form_field in sorted(active_fields.values(), key=lambda item: (item.sequence, item.id))
        ]
        self.write({'state': 'map_fields'})
        return self.action_open()

    def _validate_snapshot_mappings(self):
        resolver = self.env['dms.pdf.value.resolver']
        for mapping in self.mapping_ids:
            if mapping.fill_mode == 'odoo_field':
                resolver.validate_path(self.target_model, mapping.source_field_path)

    def _save_default_mappings(self):
        self.ensure_one()
        if not self.save_mapping_as_default:
            return
        self.source_file_id._check_pdf_configuration_write()
        self.env.cr.execute('SELECT id FROM dms_file WHERE id = %s FOR UPDATE', [self.source_file_id.id])
        current = self.source_file_id._pdf_raw_content()
        if hashlib.sha256(current).hexdigest() != self.source_file_checksum:
            raise ValidationError(_('The DMS PDF changed. Restart the wizard before saving mappings.'))
        for snapshot in self.mapping_ids:
            mapping = self.env['dms.pdf.field.mapping'].with_context(active_test=False).search([
                ('form_field_id', '=', snapshot.form_field_id.id),
                ('target_model', '=', self.target_model),
            ], limit=1)
            values = {
                'fill_mode': snapshot.fill_mode,
                'source_field_path': snapshot.source_field_path if snapshot.fill_mode == 'odoo_field' else False,
                'active': True,
                'last_validated_at': fields.Datetime.now(),
            }
            if mapping:
                mapping.write(values)
            else:
                values.update({
                    'form_field_id': snapshot.form_field_id.id,
                    'target_model': self.target_model,
                })
                self.env['dms.pdf.field.mapping'].create(values)

    def action_prepare_values(self):
        self._check_owner()
        records = self._selected_records()
        self._validate_snapshot_mappings()
        self._save_default_mappings()
        resolver = self.env['dms.pdf.value.resolver']
        commands = []
        for record in records:
            value_commands = []
            for mapping in self.mapping_ids:
                value = ''
                if mapping.fill_mode == 'odoo_field':
                    value = resolver.resolve(record, self.target_model, mapping.source_field_path)
                value_commands.append(Command.create({
                    'mapping_id': mapping.id,
                    'pdf_field_name': mapping.pdf_field_name,
                    'label': mapping.label,
                    'multiline': mapping.multiline,
                    'fill_mode': mapping.fill_mode,
                    'value': value,
                }))
            email = record.work_email if self.target_model == 'employee' else record.email
            chat_partner = (
                record.user_id.partner_id if self.target_model == 'employee'
                else record
            )
            commands.append(Command.create({
                'target_res_id': record.id,
                'display_name_snapshot': record.display_name,
                'email_to': email,
                'chat_partner_id': chat_partner.id,
                'value_ids': value_commands,
            }))
        self.recipient_ids = [Command.clear()] + commands
        first = self.recipient_ids[:1]
        self.write({
            'current_recipient_id': first.id,
            'current_index': 0,
            'state': 'enter_values',
        })
        return self.action_open()

    def action_previous_recipient(self):
        self._check_owner()
        if self.current_index <= 0:
            raise UserError(_('This is the first recipient.'))
        recipients = self.recipient_ids.sorted('id')
        index = self.current_index - 1
        self.write({'current_index': index, 'current_recipient_id': recipients[index].id})
        return self.action_open()

    def action_next_recipient(self):
        self._check_owner()
        recipients = self.recipient_ids.sorted('id')
        if self.current_index >= len(recipients) - 1:
            self.write({'state': 'review'})
            return self.action_open()
        index = self.current_index + 1
        self.write({'current_index': index, 'current_recipient_id': recipients[index].id})
        return self.action_open()

    def _values_for_recipient(self, recipient):
        model = self.env[TARGET_MODEL_NAMES[self.target_model]]
        record = model.browse(recipient.target_res_id).exists()
        if not record:
            raise ValidationError(_('Recipient "%(name)s" no longer exists.', name=recipient.display_name_snapshot))
        record.check_access('read')
        resolver = self.env['dms.pdf.value.resolver']
        values = {}
        for item in recipient.value_ids:
            if item.fill_mode == 'odoo_field':
                values[item.pdf_field_name] = resolver.resolve(
                    record, self.target_model, item.mapping_id.source_field_path,
                )
            else:
                values[item.pdf_field_name] = item.value or ''
        return values

    def _generate_recipient(self, recipient, readonly=True):
        values = self._values_for_recipient(recipient)
        result = render_pdf(base64.b64decode(self.source_pdf), values, readonly=readonly)
        return result

    def action_preview_current(self):
        self._check_owner()
        recipient = self.current_recipient_id
        if not recipient:
            raise ValidationError(_('Select a recipient to preview.'))
        result = self._generate_recipient(recipient, readonly=False)
        recipient.write({
            'preview_pdf': base64.b64encode(result),
            'preview_filename': safe_pdf_filename(
                self.source_filename, recipient.display_name_snapshot, recipient.target_res_id,
            ),
            'preview_stale': False,
        })
        return self.action_open()

    def _archive_results(self, channel):
        if not self.retention_days:
            return self.env['dms.pdf.generation.batch']
        paths = sorted(set(self.mapping_ids.filtered(
            lambda item: item.fill_mode == 'odoo_field'
        ).mapped('source_field_path')))
        batch = self.env['dms.pdf.generation.batch'].create({
            'source_file_id': self.source_file_id.id,
            'source_checksum': self.source_file_checksum,
            'source_filename': self.source_filename,
            'target_model': self.target_model,
            'channel': channel,
            'expires_at': fields.Datetime.now() + relativedelta(days=self.retention_days),
            'field_paths_audit': '\n'.join(paths),
            'target_res_ids_audit': ','.join(str(item) for item in self.recipient_ids.mapped(
                'target_res_id'
            )),
        })
        for recipient in self.recipient_ids:
            attachment = self.env['ir.attachment'].create({
                'name': recipient.output_filename,
                'datas': recipient.output_pdf,
                'mimetype': 'application/pdf',
                'res_model': 'dms.pdf.generation.result',
                'res_id': 0,
            })
            result = self.env['dms.pdf.generation.result'].create({
                'batch_id': batch.id,
                'target_res_id': recipient.target_res_id,
                'recipient_display_name': recipient.display_name_snapshot,
                'output_filename': recipient.output_filename,
                'output_checksum': recipient.output_checksum,
                'attachment_id': attachment.id,
            })
            attachment.write({'res_id': result.id})
            recipient.generation_result_id = result.id
        batch.state = 'ready'
        self.batch_id = batch.id
        return batch

    def action_generate(self, channel='download'):
        self._check_owner()
        self.env.cr.execute(
            'SELECT id FROM dms_pdf_autocomplete_wizard WHERE id = %s FOR UPDATE', [self.id],
        )
        self.invalidate_recordset()
        if self.state == 'ready' and all(self.recipient_ids.mapped('output_pdf')):
            return
        if self.state in ('generating', 'sending', 'done'):
            raise UserError(_('This PDF batch is already being processed.'))
        try:
            source_pdf = base64.b64decode(self.source_pdf, validate=True)
        except (TypeError, ValueError) as error:
            raise ValidationError(_('The PDF snapshot is not valid base64 data.')) from error
        if hashlib.sha256(source_pdf).hexdigest() != self.source_file_checksum:
            raise ValidationError(_('The PDF snapshot checksum is invalid. Restart the wizard.'))
        self.write({'state': 'generating'})
        try:
            for recipient in self.recipient_ids:
                output = self._generate_recipient(recipient, readonly=True)
                recipient.write({
                    'output_pdf': base64.b64encode(output),
                    'output_filename': safe_pdf_filename(
                        self.source_filename, recipient.display_name_snapshot, recipient.target_res_id,
                    ),
                    'output_checksum': hashlib.sha256(output).hexdigest(),
                    'delivery_state': 'ready',
                    'delivery_error': False,
                })
            self._archive_results(channel)
            self.write({'state': 'ready'})
        except Exception:
            self.recipient_ids.write({
                'output_pdf': False,
                'output_filename': False,
                'output_checksum': False,
                'delivery_state': 'pending',
            })
            self.write({'state': 'failed'})
            raise

    def action_download(self):
        self.action_generate(channel='download')
        minutes = max(1, int(self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.download_token_minutes', 10,
        )))
        token = secrets.token_urlsafe(32)
        self.write({
            'download_token': token,
            'download_token_expires_at': fields.Datetime.now() + relativedelta(minutes=minutes),
            'download_token_used': False,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/dms/pdf-autocomplete/{self.id}/download?token={token}',
            'target': 'self',
        }

    def _build_zip(self):
        """Build a bounded ZIP from already generated per-recipient snapshots."""
        self._check_owner()
        if len(self.recipient_ids) > self._max_batch_size():
            raise ValidationError(_('The selected batch exceeds the configured recipient limit.'))
        limit_mb = max(1, int(self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.max_zip_uncompressed_mb', 250,
        )))
        total = 0
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for recipient in self.recipient_ids:
                document = base64.b64decode(recipient.output_pdf or b'')
                total += len(document)
                if total > limit_mb * 1024 * 1024:
                    raise ValidationError(_('The generated ZIP exceeds the configured size limit.'))
                archive.writestr(recipient.output_filename, document)
        return stream.getvalue()

    def _consume_download_token(self, token):
        """Validate and atomically consume a private ZIP download token."""
        self._check_owner()
        self.env.cr.execute(
            'SELECT id FROM dms_pdf_autocomplete_wizard WHERE id = %s FOR UPDATE', [self.id],
        )
        self.invalidate_recordset()
        if (
            not token
            or not secrets.compare_digest(token, self.download_token or '')
            or self.download_token_used
            or not self.download_token_expires_at
            or self.download_token_expires_at < fields.Datetime.now()
            or self.state != 'ready'
        ):
            raise AccessError(_('The PDF download token is invalid or expired.'))
        content = self._build_zip()
        self.write({'download_token_used': True})
        return content

    def action_open_delivery(self):
        self.action_generate(channel='email')
        delivery = self.env['dms.pdf.autocomplete.delivery.wizard'].create({
            'source_wizard_id': self.id,
            'retention_days': self.retention_days,
        })
        delivery._copy_recipients()
        return delivery.action_open()


class DmsPdfAutocompleteMapping(models.TransientModel):
    _name = 'dms.pdf.autocomplete.mapping'
    _description = 'DMS PDF Autocomplete Mapping Snapshot'
    _order = 'form_field_id, id'

    wizard_id = fields.Many2one('dms.pdf.autocomplete.wizard', required=True, ondelete='cascade')
    form_field_id = fields.Many2one('dms.pdf.form.field', required=True, readonly=True)
    pdf_field_name = fields.Char(required=True, readonly=True)
    label = fields.Char(required=True, readonly=True)
    multiline = fields.Boolean(readonly=True)
    fill_mode = fields.Selection(
        [('manual', 'Manual input'), ('odoo_field', 'Odoo field')],
        default='manual',
        required=True,
    )
    source_field_path = fields.Char()
    target_res_model = fields.Char(related='wizard_id.target_res_model', readonly=True)

    @api.onchange('fill_mode')
    def _onchange_fill_mode(self):
        if self.fill_mode == 'manual':
            self.source_field_path = False


class DmsPdfAutocompleteRecipient(models.TransientModel):
    _name = 'dms.pdf.autocomplete.recipient'
    _description = 'DMS PDF Autocomplete Recipient Snapshot'

    wizard_id = fields.Many2one('dms.pdf.autocomplete.wizard', required=True, ondelete='cascade')
    target_res_id = fields.Integer(required=True, readonly=True)
    display_name_snapshot = fields.Char(required=True, readonly=True)
    email_to = fields.Char()
    chat_partner_id = fields.Many2one('res.partner')
    value_ids = fields.One2many('dms.pdf.autocomplete.value', 'recipient_id')
    manual_value_ids = fields.One2many(
        'dms.pdf.autocomplete.value', 'recipient_id',
        domain=[('fill_mode', '=', 'manual')],
    )
    automatic_value_ids = fields.One2many(
        'dms.pdf.autocomplete.value', 'recipient_id',
        domain=[('fill_mode', '=', 'odoo_field')],
    )
    preview_pdf = fields.Binary(attachment=True, readonly=True)
    preview_filename = fields.Char(readonly=True)
    preview_stale = fields.Boolean(default=True, readonly=True)
    output_pdf = fields.Binary(attachment=True, readonly=True)
    output_filename = fields.Char(readonly=True)
    output_checksum = fields.Char(readonly=True)
    delivery_state = fields.Selection(
        [('pending', 'Pending'), ('ready', 'Ready'), ('sent', 'Sent'),
         ('failed', 'Failed'), ('skipped', 'Skipped')],
        default='pending',
        readonly=True,
    )
    delivery_error = fields.Char(readonly=True)
    generation_result_id = fields.Many2one('dms.pdf.generation.result', readonly=True)


class DmsPdfAutocompleteValue(models.TransientModel):
    _name = 'dms.pdf.autocomplete.value'
    _description = 'DMS PDF Autocomplete Value Snapshot'
    _order = 'mapping_id, id'

    recipient_id = fields.Many2one('dms.pdf.autocomplete.recipient', required=True, ondelete='cascade')
    mapping_id = fields.Many2one('dms.pdf.autocomplete.mapping', required=True, readonly=True)
    pdf_field_name = fields.Char(required=True, readonly=True)
    label = fields.Char(required=True, readonly=True)
    multiline = fields.Boolean(readonly=True)
    fill_mode = fields.Selection(
        [('manual', 'Manual input'), ('odoo_field', 'Odoo field')], required=True, readonly=True,
    )
    value = fields.Text()

    def write(self, values):
        result = super().write(values)
        if 'value' in values:
            recipients = self.mapped('recipient_id')
            recipients.write({
                'preview_stale': True,
                'preview_pdf': False,
                'preview_filename': False,
                'output_pdf': False,
                'output_filename': False,
                'output_checksum': False,
                'delivery_state': 'pending',
            })
            recipients.mapped('wizard_id').filtered(
                lambda wizard: wizard.state in ('ready', 'review')
            ).write({'state': 'enter_values'})
        return result
