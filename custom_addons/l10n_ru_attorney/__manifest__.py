{
    'name': "Россия - Доверенности",

    'summary': "Модуль для создания и печати доверенностей на получение ТМЦ",

    'description': """
Модуль доверенностей
===================

Модуль предоставляет функционал для создания, управления и печати доверенностей на получение товарно-материальных ценностей (ТМЦ) в соответствии с российским законодательством.

📋 ОСНОВНЫЕ ФУНКЦИИ:
    - Создание доверенностей на получение ТМЦ
    - Привязка к заказам на покупку
    - Указание уполномоченных лиц из справочника сотрудников
    - Контроль сроков действия доверенностей
    - Печать в формате PDF с российским оформлением
    - Интеграция с модулями Покупок и HR

📖 КАК ИСПОЛЬЗОВАТЬ:
    1. Перейдите в меню "Покупки" → "Доверенности"
    2. Нажмите "Создать" для создания новой доверенности
    3. Заполните обязательные поля:
        - Контрагент-поставщик
        - Заказ на покупку (опционально)
        - Сотрудник, который получает доверенность
        - Дата выдачи и срок действия
    4. Сохраните доверенность
    5. Для печати воспользуйтесь меню "Действия" или настройте отчет через "Настройки" → "Техническое" → "Отчеты"

⚠️ ВАЖНО:
    - Необходимо настроить справочник сотрудников с паспортными данными
    - Компания должна иметь заполненные российские реквизиты
    - Контрагенты должны быть настроены как поставщики
    """,

    'author': "MK.Lab",
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],
    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, changed hr to hr_contract dependency,
    # standardized naming and structure
    # Original author and support: MK.Lab
    'license': 'AGPL-3',

    'category': 'Localization/Russia',
    'version': "1.0.0",

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'sale', 'purchase', 'hr_contract', 'l10n_ru_base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/base_consent_views.xml',
        'views/hr_employee_views.xml',
        'views/purchase_order_views.xml',
        'report/consent_report.xml',
    ],
    'installable': True,
    'auto_install': True,
}