def post_init_hook(env):
    """Restore the size of DMS files created before this fix was installed."""
    env["dms.file"].sudo().search([])._recompute_content_size()
