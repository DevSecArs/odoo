# PDF Form Core

Technical Odoo 18 addon providing a small shared API for strict text AcroForm
validation and rendering.

```python
from odoo.addons.pdf_form_core.services import inspect_pdf, render_pdf

fields = inspect_pdf(source_bytes, max_size=10 * 1024 * 1024)
result = render_pdf(source_bytes, values, readonly=True)
```

Only unencrypted AcroForms with unique, unambiguous `/Tx` fields and exactly
one widget per field are accepted. XFA, signatures, buttons, checkboxes,
choices, orphan widgets, cyclic hierarchies, and malformed PDFs are rejected.

The addon has no dependency on HR, DMS, Mail, or other business modules.
