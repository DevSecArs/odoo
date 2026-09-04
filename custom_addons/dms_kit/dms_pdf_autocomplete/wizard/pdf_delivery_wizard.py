from odoo import Command, _, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError


class DmsPdfAutocompleteDeliveryWizard(models.TransientModel):
    _name = 'dms.pdf.autocomplete.delivery.wizard'
    _description = 'DMS PDF Delivery Confirmation'

    owner_user_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user, readonly=True,
    )
    source_wizard_id = fields.Many2one(
        'dms.pdf.autocomplete.wizard', required=True, readonly=True, ondelete='cascade',
    )
    delivery_channel = fields.Selection(
        [('email', 'Email'), ('chat', 'Odoo chat')], default='email', required=True,
    )
    subject = fields.Char(default=lambda self: _('Personal document'), required=True)
    body_html = fields.Html(default=lambda self: _('<p>Your personal document is attached.</p>'), sanitize=True)
    retention_days = fields.Integer(readonly=True)
    recipient_ids = fields.One2many('dms.pdf.autocomplete.delivery.recipient', 'delivery_wizard_id')
    state = fields.Selection(
        [('draft', 'Draft'), ('sending', 'Sending'), ('done', 'Done'), ('partial', 'Partially sent')],
        default='draft',
        readonly=True,
    )

    def _check_owner(self):
        self.ensure_one()
        if self.owner_user_id != self.env.user:
            raise AccessError(_('You cannot access another user’s delivery wizard.'))
        self.source_wizard_id._check_owner()

    def _copy_recipients(self):
        self._check_owner()
        if self.recipient_ids:
            return
        self.recipient_ids = [Command.create({
            'source_recipient_id': recipient.id,
            'send_enabled': True,
            'display_name_snapshot': recipient.display_name_snapshot,
            'output_filename': recipient.output_filename,
            'email_to': recipient.email_to,
            'chat_partner_id': recipient.chat_partner_id.id,
        }) for recipient in self.source_wizard_id.recipient_ids]

    def action_open(self):
        self._check_owner()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'dms_pdf_autocomplete.action_pdf_delivery_wizard'
        )
        action.update({'res_id': self.id, 'target': 'new'})
        return action

    def _validate_rows(self):
        enabled = self.recipient_ids.filtered('send_enabled')
        if not enabled:
            raise ValidationError(_('Enable at least one recipient.'))
        for row in enabled:
            if self.delivery_channel == 'email':
                if not row.email_to or not tools.email_normalize(row.email_to, strict=False):
                    raise ValidationError(_(
                        'Enter a valid email address for "%(name)s".', name=row.display_name_snapshot,
                    ))
            else:
                partner = row.chat_partner_id
                users = partner.user_ids.filtered(lambda user: user.active and not user.share)
                if not partner or not users:
                    raise ValidationError(_(
                        'Contact "%(name)s" has no active internal Odoo user.',
                        name=row.display_name_snapshot,
                    ))

    def _send_email(self, row):
        recipient = row.source_recipient_id
        attachment = self.env['ir.attachment'].create({
            'name': recipient.output_filename,
            'datas': recipient.output_pdf,
            'mimetype': 'application/pdf',
            'res_model': 'mail.mail',
            'res_id': 0,
        })
        mail = self.env['mail.mail'].create({
            'subject': self.subject,
            'body_html': self.body_html,
            'email_to': tools.email_normalize(row.email_to, strict=False),
            'attachment_ids': [Command.link(attachment.id)],
        })
        attachment.write({'res_id': mail.id})
        row.write({'delivery_state': 'sent', 'mail_id': mail.id, 'delivery_error': False})
        recipient.write({'delivery_state': 'sent', 'delivery_error': False})
        if recipient.generation_result_id:
            recipient.generation_result_id.write({
                'delivery_state': 'sent', 'mail_id': mail.id, 'delivery_error': False,
            })

    def _send_chat(self, row):
        recipient = row.source_recipient_id
        partner_ids = [row.chat_partner_id.id]
        channel = self.env['discuss.channel'].channel_get(partner_ids)
        attachment = self.env['ir.attachment'].create({
            'name': recipient.output_filename,
            'datas': recipient.output_pdf,
            'mimetype': 'application/pdf',
            'res_model': 'discuss.channel',
            'res_id': channel.id,
        })
        message = channel.message_post(
            body=self.body_html,
            subject=self.subject,
            message_type='comment',
            attachment_ids=[attachment.id],
        )
        row.write({'delivery_state': 'sent', 'message_id': message.id, 'delivery_error': False})
        recipient.write({'delivery_state': 'sent', 'delivery_error': False})
        if recipient.generation_result_id:
            recipient.generation_result_id.write({
                'delivery_state': 'sent', 'message_id': message.id, 'delivery_error': False,
            })

    def action_send(self):
        self._check_owner()
        self.env.cr.execute(
            'SELECT id FROM dms_pdf_autocomplete_delivery_wizard WHERE id = %s FOR UPDATE', [self.id],
        )
        self.invalidate_recordset()
        if self.state == 'done':
            return {'type': 'ir.actions.act_window_close'}
        if self.state == 'sending':
            raise UserError(_('This delivery is already being processed.'))
        self._validate_rows()
        self.write({'state': 'sending'})
        if self.source_wizard_id.batch_id:
            self.source_wizard_id.batch_id.channel = self.delivery_channel
        failed = False
        for row in self.recipient_ids.filtered('send_enabled'):
            if row.delivery_state == 'sent':
                continue
            try:
                with self.env.cr.savepoint():
                    if self.delivery_channel == 'email':
                        self._send_email(row)
                    else:
                        self._send_chat(row)
            except Exception as error:
                failed = True
                row.write({'delivery_state': 'failed', 'delivery_error': str(error)[:500]})
                row.source_recipient_id.write({
                    'delivery_state': 'failed', 'delivery_error': str(error)[:500],
                })
                if row.source_recipient_id.generation_result_id:
                    row.source_recipient_id.generation_result_id.write({
                        'delivery_state': 'failed', 'delivery_error': str(error)[:500],
                    })
        skipped = self.recipient_ids.filtered(lambda row: not row.send_enabled)
        skipped.write({'delivery_state': 'skipped'})
        skipped.mapped('source_recipient_id').write({'delivery_state': 'skipped'})
        skipped.mapped('source_recipient_id.generation_result_id').write({
            'delivery_state': 'skipped',
        })
        self.write({'state': 'partial' if failed else 'done'})
        self.source_wizard_id.write({'state': 'failed' if failed else 'done'})
        if self.source_wizard_id.batch_id:
            self.source_wizard_id.batch_id.state = 'partial' if failed else 'done'
        return self.action_open() if failed else {'type': 'ir.actions.act_window_close'}


class DmsPdfAutocompleteDeliveryRecipient(models.TransientModel):
    _name = 'dms.pdf.autocomplete.delivery.recipient'
    _description = 'DMS PDF Delivery Recipient'

    delivery_wizard_id = fields.Many2one(
        'dms.pdf.autocomplete.delivery.wizard', required=True, ondelete='cascade',
    )
    source_recipient_id = fields.Many2one(
        'dms.pdf.autocomplete.recipient', required=True, readonly=True, ondelete='cascade',
    )
    send_enabled = fields.Boolean(default=True)
    display_name_snapshot = fields.Char(readonly=True)
    output_filename = fields.Char(readonly=True)
    email_to = fields.Char()
    chat_partner_id = fields.Many2one('res.partner')
    delivery_state = fields.Selection(
        [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')],
        default='pending',
        readonly=True,
    )
    delivery_error = fields.Char(readonly=True)
    mail_id = fields.Many2one('mail.mail', readonly=True)
    message_id = fields.Many2one('mail.message', readonly=True)
