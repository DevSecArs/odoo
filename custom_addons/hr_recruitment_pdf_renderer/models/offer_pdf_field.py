from odoo import _, fields, models
from odoo.exceptions import ValidationError


DEFAULT_SOURCES = [
    ('manual', 'Manual input'),
    ('candidate_name', 'Candidate name'),
    ('candidate_address', 'Candidate address'),
    ('job_name', 'Job position'),
    ('department_name', 'Department'),
    ('salary_proposed', 'Proposed salary'),
    ('current_date', 'Current date'),
    ('company_name', 'Company name'),
    ('recruiter_name', 'Recruiter name'),
    ('static', 'Static text'),
]


class OfferPdfField(models.Model):
    _name = 'mail.template.offer.pdf.field'
    _description = 'Manual PDF Document Field'
    _order = 'sequence, id'

    document_id = fields.Many2one('mail.template.offer.pdf.document', required=True, ondelete='cascade', index=True)
    pdf_field_name = fields.Char(string='PDF field name', required=True, readonly=True)
    label = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    default_source = fields.Selection(
        DEFAULT_SOURCES,
        string='Initial value source',
        required=True,
        default='manual',
        help='Select a safe applicant field to prefill this PDF field, or choose static text.',
    )
    default_text = fields.Text(
        string='Static initial value',
        help='Literal text used only when the initial value source is Static text.',
    )
    required = fields.Boolean(string='Required')
    multiline = fields.Boolean(string='Multiline', readonly=True)
    active = fields.Boolean(default=True, help='Disabled because this field is no longer present in the uploaded PDF.')

    _sql_constraints = [
        ('offer_pdf_field_name_unique', 'unique(document_id, pdf_field_name)', 'PDF field names must be unique per document.'),
    ]

    def _get_default_value(self, applicant):
        self.ensure_one()
        applicant.ensure_one()
        source = self.default_source
        if source == 'manual':
            return ''
        if source == 'candidate_name':
            return applicant.partner_name or ''
        if source == 'candidate_address':
            return self._get_candidate_address(applicant)
        if source == 'job_name':
            return applicant.job_id.name or ''
        if source == 'department_name':
            return applicant.department_id.name or ''
        if source == 'salary_proposed':
            currency = applicant.company_id.currency_id
            return self.env['ir.qweb.field.monetary'].value_to_html(applicant.salary_proposed or 0.0, {'display_currency': currency})
        if source == 'current_date':
            return fields.Date.to_string(fields.Date.context_today(self))
        if source == 'company_name':
            return applicant.company_id.name or ''
        if source == 'recruiter_name':
            return applicant.user_id.name or ''
        if source == 'static':
            return self.default_text or ''
        raise ValidationError(_('Unsupported PDF default source.'))

    @staticmethod
    def _get_candidate_address(applicant):
        """Return only physical address components, never a partner display name or email."""
        partner = applicant.partner_id
        if not partner:
            return ''
        address_fields = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')
        if not any(partner[field_name] for field_name in address_fields):
            return ''
        return (partner._display_address(without_company=True) or '').strip()
