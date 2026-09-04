import re
import unicodedata

from odoo import _, api, models, tools
from odoo.exceptions import ValidationError
from odoo.tools import format_amount, format_date, format_datetime, formatLang

from .pdf_field_mapping import FIELD_PATH_RE


CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
TARGET_MODELS = {'employee': 'hr.employee', 'partner': 'res.partner'}
RELATIONAL_TYPES = {'many2one', 'one2many', 'many2many'}


class DmsPdfValueResolver(models.AbstractModel):
    _name = 'dms.pdf.value.resolver'
    _description = 'DMS PDF Safe Field Resolver'

    @api.model
    def _model_name(self, target_model):
        try:
            return TARGET_MODELS[target_model]
        except KeyError as error:
            raise ValidationError(_('Unsupported target model.')) from error

    @api.model
    def _max_length(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'dms_pdf_autocomplete.max_output_text_length', 10000,
        )
        return max(1, int(value))

    @api.model
    def validate_path(self, target_model, path):
        if not path or not FIELD_PATH_RE.fullmatch(path):
            raise ValidationError(_('The Odoo field path is invalid.'))
        model = self.env[self._model_name(target_model)]
        parts = path.split('.')
        for index, part in enumerate(parts):
            field = model._fields.get(part)
            if not field:
                raise ValidationError(_(
                    'Field "%(field)s" does not exist on model "%(model)s".',
                    field=part,
                    model=model._description,
                ))
            model.check_field_access_rights('read', [part])
            final = index == len(parts) - 1
            if not final:
                if field.type not in RELATIONAL_TYPES:
                    raise ValidationError(_('Only relational fields may be followed in a field path.'))
                model = self.env[field.comodel_name]
            elif field.type in ('binary', 'image'):
                raise ValidationError(_('Binary and image fields cannot be written to a PDF text field.'))
        return True

    @api.model
    def resolve(self, record, target_model, path):
        self.validate_path(target_model, path)
        expected_model = self._model_name(target_model)
        if record._name != expected_model:
            raise ValidationError(_('The selected record does not match the target model.'))
        record.check_access('read')
        current = record
        final_field = None
        container = record
        parts = path.split('.')
        for index, part in enumerate(parts):
            current.check_access('read')
            current.check_field_access_rights('read', [part])
            final_field = current._fields[part]
            container = current
            if index < len(parts) - 1 or final_field.type in RELATIONAL_TYPES:
                current = current.mapped(part)
            elif len(current) == 1:
                current = current[part]
            else:
                current = [item[part] for item in current]
        if isinstance(current, list):
            value = ', '.join(
                self._format_value(item, final_field, item[final_field.name])
                for item in container
            )
        else:
            value = self._format_value(container[:1], final_field, current)
        value = CONTROL_RE.sub('', unicodedata.normalize('NFC', value or ''))
        if len(value) > self._max_length():
            raise ValidationError(_(
                'The value for field "%(field)s" exceeds the allowed length.', field=path,
            ))
        return value

    @api.model
    def _format_value(self, source, field, value):
        if field.type == 'boolean':
            return _('Yes') if value else _('No')
        if value is False or value is None:
            return ''
        if field.type in ('char', 'text'):
            return str(value)
        if field.type == 'html':
            return tools.html2plaintext(str(value))
        if field.type == 'date':
            return format_date(self.env, value)
        if field.type == 'datetime':
            return format_datetime(self.env, value)
        if field.type == 'selection':
            labels = dict(field._description_selection(self.env))
            return str(labels.get(value, value))
        if field.type == 'monetary':
            currency_name = field.get_currency_field(source)
            currency = source[currency_name]
            return format_amount(self.env, value, currency) if currency else str(value)
        if field.type in ('float', 'integer'):
            return formatLang(self.env, value)
        if field.type in RELATIONAL_TYPES or field.type == 'reference':
            records = value if hasattr(value, 'mapped') else self.env[field.comodel_name].browse()
            records.check_access('read')
            return ', '.join(records.mapped('display_name'))
        raise ValidationError(_('Field type "%(type)s" is not supported.', type=field.type))
