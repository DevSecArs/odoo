from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DmsPdfGenerationBatch(models.Model):
    _name = 'dms.pdf.generation.batch'
    _description = 'DMS PDF Generation Batch'
    _order = 'create_date desc, id desc'

    source_file_id = fields.Many2one('dms.file', ondelete='set null', index=True)
    source_checksum = fields.Char(required=True, readonly=True)
    source_filename = fields.Char(required=True, readonly=True)
    target_model = fields.Selection(
        [('employee', 'Employee'), ('partner', 'Contact')], required=True, readonly=True,
    )
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    channel = fields.Selection(
        [('download', 'Download'), ('email', 'Email'), ('chat', 'Odoo chat')],
        required=True,
        readonly=True,
    )
    state = fields.Selection(
        [('generating', 'Generating'), ('ready', 'Ready'), ('partial', 'Partially delivered'),
         ('done', 'Done'), ('failed', 'Failed')],
        default='generating',
        required=True,
        readonly=True,
    )
    expires_at = fields.Datetime(required=True, readonly=True, index=True)
    result_ids = fields.One2many('dms.pdf.generation.result', 'batch_id', readonly=True)
    success_count = fields.Integer(compute='_compute_counts', store=True)
    error_count = fields.Integer(compute='_compute_counts', store=True)
    field_paths_audit = fields.Text(readonly=True)
    target_res_ids_audit = fields.Text(readonly=True)

    @api.depends('result_ids.delivery_state')
    def _compute_counts(self):
        for batch in self:
            batch.success_count = len(batch.result_ids.filtered(
                lambda result: result.delivery_state in ('ready', 'sent'),
            ))
            batch.error_count = len(batch.result_ids.filtered(
                lambda result: result.delivery_state == 'failed',
            ))

    @api.model
    def _cron_cleanup_expired(self):
        limit = max(1, int(self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.cleanup_batch_size', 100,
        )))
        expired = self.search([('expires_at', '<=', fields.Datetime.now())], limit=limit)
        expired.mapped('result_ids.attachment_id').unlink()
        expired.unlink()


class DmsPdfGenerationResult(models.Model):
    _name = 'dms.pdf.generation.result'
    _description = 'DMS PDF Generation Result'
    _order = 'id'

    batch_id = fields.Many2one(
        'dms.pdf.generation.batch', required=True, ondelete='cascade', index=True,
    )
    user_id = fields.Many2one(related='batch_id.user_id', store=True, readonly=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True, readonly=True)
    target_model = fields.Selection(related='batch_id.target_model', store=True, readonly=True)
    target_res_id = fields.Integer(required=True, readonly=True)
    recipient_display_name = fields.Char(required=True, readonly=True)
    output_filename = fields.Char(required=True, readonly=True)
    output_checksum = fields.Char(required=True, readonly=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null', readonly=True)
    delivery_state = fields.Selection(
        [('ready', 'Ready'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')],
        default='ready',
        required=True,
        readonly=True,
    )
    delivery_error = fields.Char(readonly=True)
    mail_id = fields.Many2one('mail.mail', ondelete='set null', readonly=True)
    message_id = fields.Many2one('mail.message', ondelete='set null', readonly=True)

    @api.constrains('target_model', 'target_res_id')
    def _check_target(self):
        for result in self:
            if result.target_model not in ('employee', 'partner') or result.target_res_id <= 0:
                raise ValidationError(_('Invalid PDF generation target.'))
