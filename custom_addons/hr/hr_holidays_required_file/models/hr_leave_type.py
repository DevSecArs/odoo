# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


DEFAULT_REQUIRED_DOCUMENT_NAME = 'Вспомогательный документ'


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    document_required = fields.Boolean(string='Требуется документ')
    required_document_name = fields.Char(
        string='Наименование требуемого документа',
        default=DEFAULT_REQUIRED_DOCUMENT_NAME,
    )

    @api.onchange('document_required')
    def _onchange_document_required(self):
        if self.document_required:
            self.support_document = True
        else:
            self.required_document_name = DEFAULT_REQUIRED_DOCUMENT_NAME

    def write(self, vals):
        if vals.get('document_required') is False:
            vals = dict(vals, required_document_name=DEFAULT_REQUIRED_DOCUMENT_NAME)
        return super().write(vals)

    @api.constrains('document_required', 'support_document')
    def _check_required_document_is_supported(self):
        for leave_type in self:
            if leave_type.document_required and not leave_type.support_document:
                raise ValidationError(
                    _(
                        'Для обязательного документа включите возможность '
                        'прикрепления документа.'
                    )
                )
