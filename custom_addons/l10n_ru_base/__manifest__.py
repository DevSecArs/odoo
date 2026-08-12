{
    'name': "Россия - Базовая локализация",
    'summary': "Основное приложение российской локализации для Odoo 18",
    'description': "Базовый модуль с централизованными настройками российской локализации",
    'author': "MK.Lab",
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],
    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, standardized naming and structure
    # Original author and support: MK.Lab
    'license': 'AGPL-3',

    'category': 'Localization/Russia',
    'version': "1.0.1",
    'depends': ['base','sale','account','sale_stock','uom','contacts','portal','website'],
    'external_dependencies': {'python' : ['pytils']},
    'data': [

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}