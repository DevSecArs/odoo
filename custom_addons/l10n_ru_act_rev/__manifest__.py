{
    'name': "Россия - Акты сверки",

    'summary': "Модуль для создания и печати актов сверки взаиморасчетов",

    'description': """
Модуль актов сверки взаиморасчетов
========================================

Модуль предоставляет возможность создания и печати актов сверки взаиморасчетов с контрагентами в соответствии с российским законодательством.

📊 ОСНОВНЫЕ ФУНКЦИИ:
    - Создание актов сверки по любому контрагенту
    - Отображение дебеторской и кредиторской задолженности
    - Фильтрация по периодам и компаниям
    - Выбор типа проводок (проведенные или все)
    - Печать в формате PDF с российским оформлением
    - Портальный доступ для клиентов

📖 КАК ИСПОЛЬЗОВАТЬ:
    1. Открыть карточку контрагента (Контакты)
    2. Нажать кнопку "Действия" → "Печать акт сверки"
    3. В мастере выбрать:
        - Компанию (для которой нужна сверка)
        - Период сверки (даты начала и окончания)
        - Тип проводок (проведенные или включая черновики)
    4. Нажать "Печать" для создания PDF-файла

⚠️ ВАЖНО:
    - Модуль работает только с проводками в модуле Выставление счетов
    - Необходимо настроить российские реквизиты компании
    - Контрагенты должны иметь проводки в системе
    """,

    'author': "MK.Lab",
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],
    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, restored website dependency,
    # standardized naming and structure
    # Original author and support: MK.Lab
    'license': 'AGPL-3',

    'category': 'Localization/Russia',
    'version': "1.0.1",

    # any module necessary for this one to work correctly
    "depends": ["account", "portal", "website", 'contacts', "l10n_ru_base", "l10n_ru_contract", "l10n_ru_doc"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/general_ledger_wizard_view.xml",
        "report/layouts.xml",
        "report/general_ledger.xml",
        "views/account_account_views.xml",
        "views/report_general_ledger.xml",
        "views/portal_templates.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "auto_install": True,
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}