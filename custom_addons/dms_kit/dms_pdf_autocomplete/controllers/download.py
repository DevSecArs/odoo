from odoo import _, http
from odoo.exceptions import AccessError
from odoo.http import content_disposition, request


class DmsPdfAutocompleteDownloadController(http.Controller):

    @http.route(
        '/dms/pdf-autocomplete/<int:wizard_id>/download',
        type='http', auth='user', methods=['GET'], csrf=False,
    )
    def download_zip(self, wizard_id, token, **kwargs):
        wizard = request.env['dms.pdf.autocomplete.wizard'].browse(wizard_id).exists()
        if not wizard or wizard.owner_user_id != request.env.user:
            raise AccessError(_('The PDF download is not available.'))
        content = wizard._consume_download_token(token)
        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', content_disposition('personalized_documents.zip')),
                ('X-Content-Type-Options', 'nosniff'),
            ],
        )
