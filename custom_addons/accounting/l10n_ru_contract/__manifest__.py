{
    'name': 'Россия - Договоры',
    
    'summary': 'Модуль для создания и управления договорами с контрагентами',

    'description': """
Модуль управления договорами
==============================

Модуль предоставляет функционал для создания, управления и печати договоров с контрагентами в соответствии с российским законодательством.

📋 ОСНОВНЫЕ ФУНКЦИИ:
    - Создание договоров с клиентами и поставщиками
    - Управление данными контрагентов (ИНН, КПП, ОГРН)
    - Генерация договоров с российским оформлением
    - Печать договоров в формате PDF
    - Автоматическое заполнение реквизитов
    - Интеграция с модулями Продаж и Покупок
    - Морфологическая обработка русских имен и фамилий

📖 КАК ИСПОЛЬЗОВАТЬ:
    1. Перейдите в меню "Продажи" → "Договоры клиентов" или "Покупки" → "Договоры поставщиков"
    2. Нажмите "Создать" для создания нового договора
    3. Заполните обязательные поля:
        - Контрагент (клиент или поставщик)
        - Номер договора
        - Дата заключения
        - Предмет договора
    4. Укажите должностные лица и их полномочия
    5. Нажмите "Печать" для создания PDF-документа

⚠️ ВАЖНО:
    - Необходимо настроить российские реквизиты компании
    - Контрагенты должны иметь заполненные реквизиты
    - Для корректной морфологической обработки установите пакет pymorphy2
    """,
    
    'version': "1.0.0",
    'sequence': 0,
    'author': 'StarlingSoft',
    'maintainer': "DOCSLY",
    'icon': '/account/static/description/l10n.png',
    'countries': ['ru'],

    # Modification notice as required by AGPL-3 license:
    # This module has been modified by DOCSLY (https://docsly.org)
    # Date of modification: 2025 (updated from Odoo 17 to Odoo 18)
    # Changes: Updated for Odoo 18 compatibility, standardized naming and structure
    # Original author and support: StarlingSoft
    'license': 'AGPL-3',
    'category': 'Localization/Russia',
    'depends': [
        'base',
        'mail',
        'account', 'sale', 'sale_management', 'purchase', 'l10n_ru_base'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/contract_customer_view.xml',
        'report/report_contract.xml',
        'report/report_contract_order.xml',
        'report/report_contract_order1.xml',
        'report/report_contract_invoce.xml',

    ],
    'installable': True,
    'auto_install': True,
}