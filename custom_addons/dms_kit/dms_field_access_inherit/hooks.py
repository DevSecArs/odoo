def post_init_hook(env):
    """Apply parent access inheritance to existing embedded directories."""
    directory_model = env["dms.directory"].sudo()
    templates = env["dms.field.template"].sudo().search(
        [("parent_directory_id", "!=", False)]
    )
    for template in templates:
        directories = directory_model.search(
            [
                ("parent_id", "=", template.parent_directory_id.id),
                ("res_model", "=", template.model),
                ("res_id", "!=", False),
            ]
        )
        directories.write({"inherit_group_ids": True})
