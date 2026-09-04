{
    'name': "Россия - Бухгалтерские документы",

    'summary': "Модуль российской локализации для печатных форм документов",

    'description': """
Модуль бухгалтерских документов для российской локализации Odoo 18
==================================================================

Этот модуль предоставляет функционал для создания печатных форм документов в соответствии с российским законодательством:

📋 ОСНОВНЫЕ ФУНКЦИИ:
    - Печатные формы документов в соответствии с российским законодательством
    - Товарная накладная (ТОРГ-12)
    - Счета на оплату и счета-фактуры
    - Акты выполненных работ
    - Универсальные передаточные документы (УПД)
    - Вывод подписей и печатей
    - Российские реквизиты компаний (ИНН, КПП, ОКПО)

📖 ИСПОЛЬЗОВАНИЕ:
    1. Установите этот модуль через основное приложение "Россия - Базовая локализация"
    2. Настройки → Общие настройки → Россия - Базовая локализация
    3. Включите модуль "Бухгалтерские документы" в панели настроек
    4. Используйте печатные формы через меню "Действия" в документах

⚠️ ВАЖНО:
    - Этот модуль должен использоваться вместе с основным приложением "Россия - Базовая локализация"
    - Для работы требуется установка дополнительных Python библиотек (pytils)
    - Модуль добавляет российские поля в компании и контрагентов
    - Поддерживает печать факсимиле и печатей в документах
    """,

    'author': "MK.Lab",
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],

    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, restructured dependencies,
    # standardized naming and documentation
    # Original author and support: MK.Lab

    'license': 'AGPL-3',
    'category': 'Localization/Russia',
    'version': "1.0.0",

    'depends': ['l10n_ru_base'],

    'external_dependencies': {'python' : ['pytils']},

    'data': [
        'views/account_invoice_view.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/res_users_view.xml',
        'views/res_bank_view.xml',
        'views/uom.xml',
        'views/tax.xml',
        'views/product.xml',
        'views/l10n_ru_doc_data.xml',
        'report/l10n_ru_doc_report.xml',
        'report/report_order.xml',
        'report/report_invoice.xml',
        'report/report_bill.xml',
        'report/report_act.xml',
        'report/report_upd.xml',
        'report/report_updn.xml',
    ],

    'demo': [
        'demo/l10n_ru_doc_demo.xml',
    ],

    'installable': True,
    'auto_install': False,
}