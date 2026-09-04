# Employee Multi Department

This Odoo 18 module lets one employee belong to several departments while
preserving the standard `department_id` as the primary department.

## Behaviour

- The primary department continues to drive the standard manager and
  organisational hierarchy logic.
- `department_ids` contains the primary department and every additional
  department. The primary membership is restored automatically if removed.
- Employee and public employee directories can be filtered by any membership.
- Department employee counters and the employee action include both primary and
  additional members.
- Existing primary memberships are migrated during module installation.

Additional memberships do not grant roles, access rights, record-rule access,
or management authority. Membership history, dates, workload allocation, and
cost allocation are not tracked by this module.

## Verification

Install or update the module on a dedicated test database, then run its tests:

```powershell
python odoo-bin -c odoo.conf -d odoo_test_multi_department --test-enable `
  --test-tags /hr_employee_multi_department -i hr_employee_multi_department `
  --stop-after-init
```

## Russian translation

Odoo loads module translations only for active database languages. On a
database where Russian has not been activated yet, load it during the first
module update:

```powershell
python odoo-bin -c odoo.conf -d <database> --load-language=ru_RU `
  -u hr_employee_multi_department --i18n-overwrite --stop-after-init
```

After `ru_RU` is active, regular module updates with `--i18n-overwrite` load
`i18n/ru.po` automatically.
