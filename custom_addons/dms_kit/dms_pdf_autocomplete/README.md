# DMS PDF Autocomplete

`dms_pdf_autocomplete` uses a PDF AcroForm stored in DMS as a template for a
batch of personalized documents. It supports contacts (`res.partner`) and
employees (`hr.employee`).

## Supported templates

The source must be an unencrypted PDF with an AcroForm containing uniquely
named text (`/Tx`) fields. Multiline text fields are supported. The first
version intentionally rejects XFA, signatures, check boxes, radio buttons,
choice fields, encrypted or damaged documents, and fields represented by
multiple widgets.

Uploading an ordinary PDF to DMS remains unchanged. Validation and field
synchronization start only when **Fill PDF** is selected. A user with read-only
DMS access can use an unchanged, previously synchronized template; write access
is required to synchronize fields or save mappings as defaults.

## Workflow

1. Open one PDF in DMS and select **Fill PDF**.
2. Select either employees or contacts and choose the recipients.
3. Map each AcroForm field to an Odoo field path or leave it as manual input.
   Employee and contact mappings are saved independently.
4. Enter manual values separately for every recipient and use the preview when
   needed.
5. Download a ZIP or confirm individual delivery by email or personal Odoo
   chat.

The field selector can follow relational fields. There is no business-field
allowlist, but every model, record, and field access check is performed as the
current user. The module does not use `sudo()` to read document values. Python
expressions, method calls, Jinja, and `safe_eval` are not accepted as mappings.
Binary and image fields cannot be rendered into text AcroForm fields.

Email creates one queued `mail.mail` per enabled recipient, with only that
recipient's PDF. Chat delivery requires an active internal Odoo user and posts
the matching PDF to a personal channel. The confirmation screen allows an
address or chat contact to be changed and individual rows to be excluded.

## Retention and confidentiality

Retention defaults to `0`: no separate batch history or archive attachment is
created. A positive number of days creates protected batch/results records and
attachments, removed by the daily cleanup job after expiry. Attachments copied
to queued email or Discuss messages are part of Odoo Mail/Discuss history and
are deliberately not removed by this module's cleanup job; their lifetime must
be controlled by the organization's mail retention policy.

Generated documents may contain confidential HR or contact data. Access is
never elevated: users only see fields and records allowed by their existing
DMS, HR, contact, company, and field-group permissions. Retained history is
limited to its owner; DMS managers can inspect history in their allowed
companies.

## Resource limits

The following `ir.config_parameter` keys can be adjusted by an administrator:

| Parameter | Default |
| --- | ---: |
| `dms_pdf_autocomplete.max_source_pdf_size_mb` | 10 MB |
| `dms_pdf_autocomplete.max_batch_size` | 100 recipients |
| `dms_pdf_autocomplete.max_output_text_length` | 10,000 characters |
| `dms_pdf_autocomplete.max_zip_uncompressed_mb` | 250 MB |
| `dms_pdf_autocomplete.download_token_minutes` | 10 minutes |
| `dms_pdf_autocomplete.cleanup_batch_size` | 100 batches |

ZIP downloads use an authenticated, short-lived, single-use token. Entry names
are normalized, contain no directories, and include the source record ID to
remain unique.

## Testing

Run only against the development database::

    python odoo-bin -c odoo.conf -d odoo-dev --test-enable --stop-after-init -u dms_pdf_autocomplete --test-tags /dms_pdf_autocomplete
