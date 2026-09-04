{
    "name": "Ссылка на договор сотрудника в DMS",
    "summary": "Выбор документа договора из каталога DMS",
    "version": "18.0.1.0.2",
    "category": "Human Resources/Employees",
    "license": "LGPL-3",
    "depends": ["hr_contract", "dms"],
    "data": [
        "views/hr_contract_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "employee_contract_dms_link/static/src/js/contract_dms_file_field.js",
            "employee_contract_dms_link/static/src/xml/contract_dms_file_field.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
