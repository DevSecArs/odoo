from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class DmsPdfFormField(models.Model):
    _name = 'dms.pdf.form.field'
    _description = 'DMS PDF Form Field'
    _order = 'sequence, id'

    file_id = fields.Many2one('dms.file', required=True, ondelete='cascade', index=True)
    pdf_field_name = fields.Char(required=True, readonly=True, index=True)
    label = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    multiline = fields.Boolean(readonly=True)
    active = fields.Boolean(default=True)
    mapping_ids = fields.One2many('dms.pdf.field.mapping', 'form_field_id')

    _sql_constraints = [(
        'dms_pdf_form_field_name_unique',
        'unique(file_id, pdf_field_name)',
        'PDF field names must be unique per DMS file.',
    )]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self.env['dms.file'].browse(values.get('file_id'))._check_pdf_configuration_write()
        return super().create(vals_list)

    def write(self, values):
        self.mapped('file_id')._check_pdf_configuration_write()
        return super().write(values)

    def unlink(self):
        self.mapped('file_id')._check_pdf_configuration_write()
        return super().unlink()

    def _check_related_file_read(self):
        files = self.mapped('file_id')
        if len(files._filtered_access('read')) != len(files):
            raise AccessError(_('You cannot access the related DMS file.'))
        return True
