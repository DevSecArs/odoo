# -*- coding: utf-8 -*-

from odoo import api, fields, models


DEFAULT_DOCUMENT_NAME = 'Вспомогательный документ'


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    leave_type_document_required = fields.Boolean(
        related='holiday_status_id.document_required',
    )
    # Kept for compatibility with already installed versions of the view.
    leave_type_required_document_name = fields.Char(
        compute='_compute_leave_type_document_names',
    )
    leave_type_document_display_name = fields.Char(
        compute='_compute_leave_type_document_names',
    )

    @api.depends(
        'holiday_status_id.document_required',
        'holiday_status_id.required_document_name',
    )
    def _compute_leave_type_document_names(self):
        for leave in self:
            document_name = (
                leave.holiday_status_id.required_document_name
                if leave.holiday_status_id.document_required
                else DEFAULT_DOCUMENT_NAME
            )
            document_name = document_name or DEFAULT_DOCUMENT_NAME
            leave.leave_type_required_document_name = document_name
            leave.leave_type_document_display_name = document_name
