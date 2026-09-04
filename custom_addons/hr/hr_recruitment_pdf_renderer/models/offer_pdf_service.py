"""Narrow, defensive AcroForm reader and writer used by the document workflow."""

import io
import re

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tools import pdf


FIELD_NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')
READ_ONLY = 1
MULTILINE = 1 << 12
MAX_PDF_SIZE = 10 * 1024 * 1024


def _resolve(value):
    """Resolve an indirect PDF object on all supported Odoo PDF backends."""
    if hasattr(value, 'get_object'):
        return value.get_object()
    return value.getObject() if hasattr(value, 'getObject') else value


def _object_key(value):
    value = _resolve(value)
    reference = getattr(value, 'indirect_reference', None) or getattr(value, 'indirectRef', None)
    if reference:
        return (getattr(reference, 'idnum', None), getattr(reference, 'generation', None))
    return id(value)


def _string(value):
    return str(value) if value is not None else ''


def _field_name(field):
    """Return a field's terminal technical name, following its parent chain."""
    seen = set()
    current = _resolve(field)
    while current:
        key = _object_key(current)
        if key in seen:
            raise ValidationError(_('The PDF contains a cyclic form field hierarchy.'))
        seen.add(key)
        name = current.get('/T')
        if name is not None:
            return _string(name)
        current = _resolve(current.get('/Parent')) if current.get('/Parent') else None
    return ''


def _field_definition(field):
    """Resolve a widget to the dictionary carrying its field type and flags."""
    seen = set()
    current = _resolve(field)
    while current:
        key = _object_key(current)
        if key in seen:
            raise ValidationError(_('The PDF contains a cyclic form field hierarchy.'))
        seen.add(key)
        if current.get('/FT'):
            return current
        current = _resolve(current.get('/Parent')) if current.get('/Parent') else None
    return None


def inspect_pdf(document):
    """Validate a PDF AcroForm and return its supported fields.

    The method deliberately accepts only one widget for every canonical field.
    This keeps the user-facing mapping unambiguous and avoids silently filling
    differently configured widgets with the same technical field name.
    """
    if not document or len(document) > MAX_PDF_SIZE:
        raise ValidationError(_('The PDF file is empty or exceeds the allowed size.'))
    if not document.startswith(b'%PDF-'):
        raise ValidationError(_('The uploaded file is not a PDF document.'))
    try:
        reader = pdf.PdfFileReader(io.BytesIO(document), strict=False)
        if reader.isEncrypted:
            raise ValidationError(_('Encrypted PDF documents are not supported.'))
        catalog = _resolve(reader.trailer['/Root'])
        acro_form = _resolve(catalog.get('/AcroForm'))
    except ValidationError:
        raise
    except (pdf.DependencyError, pdf.PdfReadError, KeyError, ValueError, TypeError) as error:
        raise ValidationError(_('The PDF document is damaged or uses an unsupported encoding.')) from error
    if not acro_form:
        raise ValidationError(_('The PDF does not contain an AcroForm.'))
    if acro_form.get('/XFA'):
        raise ValidationError(_('XFA PDF forms are not supported. Use AcroForm text fields.'))
    roots = acro_form.get('/Fields')
    if not roots:
        raise ValidationError(_('The PDF AcroForm does not contain any fields.'))

    canonical = {}
    canonical_keys = set()

    def visit(field):
        field = _resolve(field)
        field_type = field.get('/FT')
        children = field.get('/Kids') or []
        if field_type:
            name = _field_name(field)
            if not name or not FIELD_NAME_RE.fullmatch(name):
                raise ValidationError(_('PDF field names may only contain letters, digits, hyphens and underscores.'))
            if name in canonical:
                raise ValidationError(_('The PDF contains duplicate field name "%(name)s".', name=name))
            if field_type != '/Tx':
                raise ValidationError(_('Only text AcroForm fields (/Tx) are supported.'))
            canonical[name] = field
            canonical_keys.add(_object_key(field))
        for child in children:
            visit(child)

    for root in roots:
        visit(root)
    if not canonical:
        raise ValidationError(_('The PDF does not contain any text AcroForm field.'))

    widgets = {}
    for page_number in range(reader.getNumPages()):
        page = reader.getPage(page_number)
        for annotation in page.get('/Annots') or []:
            widget = _resolve(annotation)
            if widget.get('/Subtype') != '/Widget':
                continue
            definition = _field_definition(widget)
            name = _field_name(widget)
            if not definition or not name or name not in canonical:
                raise ValidationError(_('The PDF contains an orphan widget annotation.'))
            if _object_key(definition) not in canonical_keys:
                raise ValidationError(_('The PDF contains an ambiguous widget annotation.'))
            if name in widgets:
                raise ValidationError(_('The PDF contains duplicate widgets for field "%(name)s".', name=name))
            widgets[name] = widget
    missing_widgets = set(canonical) - set(widgets)
    if missing_widgets:
        raise ValidationError(_('The PDF field "%(name)s" has no widget annotation.', name=sorted(missing_widgets)[0]))

    return [
        {
            'name': name,
            'label': _string(field.get('/TU')) or name,
            'multiline': bool(int(field.get('/Ff', 0)) & MULTILINE),
        }
        for name, field in canonical.items()
    ]


def _walk_widgets(reader):
    for page_number in range(reader.getNumPages()):
        page = reader.getPage(page_number)
        for annotation in page.get('/Annots') or []:
            widget = _resolve(annotation)
            if widget.get('/Subtype') == '/Widget':
                yield widget, _field_definition(widget), _field_name(widget)


def render_pdf(document, values, readonly=False):
    """Fill a verified PDF and validate the generated result before returning bytes."""
    expected = {str(name): str(value or '') for name, value in values.items()}
    fields = {field['name'] for field in inspect_pdf(document)}
    if fields != set(expected):
        raise ValidationError(_('PDF fields changed since the document configuration was saved.'))
    try:
        reader = pdf.PdfFileReader(io.BytesIO(document), strict=False)
        writer = pdf.PdfFileWriter()
        for page_number in range(reader.getNumPages()):
            writer.addPage(reader.getPage(page_number))
        writer._root_object.update({
            pdf.NameObject('/AcroForm'): reader.trailer['/Root']['/AcroForm'],
        })
        pdf.fill_form_fields_pdf(writer, expected)
        if readonly:
            for page_number in range(writer.getNumPages()):
                for annotation in writer.getPage(page_number).get('/Annots') or []:
                    widget = _resolve(annotation)
                    if widget.get('/Subtype') != '/Widget':
                        continue
                    definition = _field_definition(widget)
                    if definition:
                        definition.update({
                            pdf.NameObject('/Ff'): pdf.NumberObject(
                                int(definition.get('/Ff', 0)) | READ_ONLY
                            ),
                        })
        stream = io.BytesIO()
        writer.write(stream)
        result = stream.getvalue()
    except (pdf.DependencyError, pdf.PdfReadError, ValueError, TypeError) as error:
        raise ValidationError(_('The PDF could not be filled. Check its form field appearance settings.')) from error

    result_reader = pdf.PdfFileReader(io.BytesIO(result), strict=False)
    resulting_values = {}
    for widget, definition, name in _walk_widgets(result_reader):
        if name not in expected or not definition:
            raise ValidationError(_('The generated PDF has an inconsistent widget structure.'))
        value = _string(definition.get('/V', widget.get('/V', '')))
        if value != expected[name]:
            raise ValidationError(_('The generated PDF did not preserve the value of field "%(name)s".', name=name))
        if readonly and not (int(definition.get('/Ff', 0)) & READ_ONLY):
            raise ValidationError(_('The generated PDF field "%(name)s" is not read-only.', name=name))
        appearance = _resolve(widget.get('/AP')) if widget.get('/AP') else None
        if not appearance or not appearance.get('/N'):
            raise ValidationError(_('The generated PDF has no normal appearance for field "%(name)s".', name=name))
        resulting_values[name] = value
    if resulting_values != expected:
        raise ValidationError(_('The generated PDF does not contain all expected fields.'))
    return result
