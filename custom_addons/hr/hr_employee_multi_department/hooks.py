def post_init_hook(env):
    """Add existing primary departments without changing any membership."""
    # A single idempotent SQL statement keeps installation scalable. The
    # relation's composite primary key makes ON CONFLICT safe on repeated runs.
    env.cr.execute("""
        INSERT INTO hr_employee_department_rel (employee_id, department_id)
        SELECT id, department_id
          FROM hr_employee
         WHERE department_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
