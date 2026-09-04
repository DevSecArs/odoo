{
    'name': 'PDF-документы для подбора персонала',
    'summary': 'Ручное заполнение PDF-документов AcroForm перед отправкой',
    'version': '18.0.1.2.3',
    'category': 'Human Resources/Recruitment',
    'license': 'LGPL-3',
    'depends': ['hr_recruitment', 'mail', 'pdf_form_core', 'web'],
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
            'hr_recruitment_pdf_renderer/static/src/scss/offer_pdf_wizard.scss',
        ],
    },
    'installable': True,
    'application': False,
}
