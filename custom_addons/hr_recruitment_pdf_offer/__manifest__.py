{
    'name': 'Recruitment PDF Documents',
    'summary': 'Manually complete AcroForm PDF documents before sending them',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Recruitment',
    'license': 'LGPL-3',
    'depends': ['hr_recruitment', 'mail', 'web'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'views/mail_template_views.xml',
        'views/hr_recruitment_stage_views.xml',
        'views/hr_applicant_views.xml',
        'wizard/offer_pdf_send_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_recruitment_pdf_offer/static/src/scss/offer_pdf_wizard.scss',
        ],
    },
    'installable': True,
    'application': False,
}
