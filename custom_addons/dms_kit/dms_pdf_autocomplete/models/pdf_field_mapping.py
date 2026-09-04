import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


FIELD_PATH_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$')


class DmsPdfFieldMapping(models.Model):
    _name = 'dms.pdf.field.mapping'
    _description = 'DMS PDF Field Mapping'

    form_field_id = fields.Many2one(
        'dms.pdf.form.field', required=True, ondelete='cascade', index=True,
    )
    target_model = fields.Selection(
        [('employee', 'Employee'), ('partner', 'Contact')], required=True, index=True,
    )
    fill_mode = fields.Selection(
        [('manual', 'Manual input'), ('odoo_field', 'Odoo field')],
        required=True,
        default='manual',
    )
    source_field_path = fields.Char()
    format_hint = fields.Selection(
        [
            ('default', 'Default'),
            ('date', 'Date'),
            ('datetime', 'Date and time'),
            ('monetary', 'Monetary'),
            ('boolean', 'Boolean'),
            ('list', 'List'),
        ],
        default='default',
        required=True,
    )
    last_validated_at = fields.Datetime(readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [(
        'dms_pdf_field_mapping_target_unique',
        'unique(form_field_id, target_model)',
        'Only one mapping per target model is allowed for each PDF field.',
    )]

    @api.constrains('fill_mode', 'source_field_path')
    def _check_source_field_path(self):
        for mapping in self:
            if mapping.fill_mode == 'manual' and mapping.source_field_path:
                raise ValidationError(_('Manual mappings cannot define an Odoo field path.'))
            if mapping.fill_mode == 'odoo_field':
                if not mapping.source_field_path or not FIELD_PATH_RE.fullmatch(mapping.source_field_path):
                    raise ValidationError(_('Select a valid Odoo field path.'))
                self.env['dms.pdf.value.resolver'].validate_path(
                    mapping.target_model, mapping.source_field_path,
                )

    @api.model_create_multi
    def create(self, vals_list):
        fields_by_id = self.env['dms.pdf.form.field'].browse(
            [values.get('form_field_id') for values in vals_list]
        )
        fields_by_id.mapped('file_id')._check_pdf_configuration_write()
        records = super().create(vals_list)
        records.filtered(lambda item: item.fill_mode == 'odoo_field').write({
            'last_validated_at': fields.Datetime.now(),
        })
        return records

    def write(self, values):
        self.mapped('form_field_id.file_id')._check_pdf_configuration_write()
        if values.get('fill_mode') == 'manual':
            values = dict(values, source_field_path=False)
        result = super().write(values)
        if {'fill_mode', 'source_field_path'} & set(values):
            self._check_source_field_path()
        return result

    def unlink(self):
        self.mapped('form_field_id.file_id')._check_pdf_configuration_write()
        return super().unlink()
