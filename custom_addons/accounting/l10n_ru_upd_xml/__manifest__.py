{
    'name': "Россия - УПД XML",

    'summary': "Модуль для создания УПД в формате XML (формат 5.01)",

    'description': """
Модуль УПД в формате XML
=============================

Модуль предоставляет возможность создания Универсальных передаточных документов (УПД) в формате XML в соответствии с российским законодательством (формат 5.01).

📊 ОСНОВНЫЕ ФУНКЦИИ:
    - Генерация УПД в формате XML 5.01
    - Поддержка всех реквизитов УПД
    - Интеграция с модулем бухгалтерского учета
    - Автоматическое заполнение реквизитов компании и контрагента
    - Поддержка справочника ОКЕИ для единиц измерения
    - Экспорт в XML-файл для передачи в электронном виде
    - Валидация соответствия формату XML

📖 КАК ИСПОЛЬЗОВАТЬ:
    1. Откройте счет или счет-фактуру в модуле Бухгалтерия
    2. Нажмите кнопку "Печать" и выберите "УПД XML"
    3. Проверьте заполненность всех обязательных полей:
        - Реквизиты компании (ИНН, КПП, ОГРН, адрес)
        - Реквизиты контрагента
        - Единицы измерения товаров/услуг (коды ОКЕИ)
    4. Нажмите "Создать XML" для генерации файла
    5. Скачайте созданный XML-файл

⚠️ ВАЖНО:
    - Необходимо настроить полные российские реквизиты компании
    - Контрагенты должны иметь заполненные реквизиты
    - Используйте только коды ОКЕИ для единиц измерения
    - Модуль требует установки библиотеки lxml
    """,

    'author': "MKLab",
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],

    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, fixed dependencies from contract to l10n_ru_contract,
    # standardized naming and structure
    # Original author and support: MKLab
    'license': 'AGPL-3',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Localization/Russia',
    'version': "1.0.0",

    # any module necessary for this one to work correctly
    'depends': ['web','base','account','l10n_ru_base','l10n_ru_contract', 'l10n_ru_doc'],

    # always loaded
    'data': [
        'views/ir_actions_report_view.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/res_users_view.xml',
        'views/views_uom_okei.xml',
        'views/view_move.xml',
        'reports/report.xml',
        'reports/upd_report.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'upd_xml/static/src/js/report/action_manager_report.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'external_dependencies': {
        'python': [
            'lxml'
        ]
    },
    'installable': True,
    'auto_install': False,
}