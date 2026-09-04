"""Validation helpers for requested Office and OpenDocument attachments.

The module never opens, converts, or executes uploaded documents.  Container
validation reduces obvious spoofing and archive attacks, but legacy OLE files
still require infrastructure-level antivirus scanning.
"""

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tools import pdf


DEFAULT_MAX_REQUESTED_FILE_SIZE = 25 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2_000
MAX_ARCHIVE_UNCOMPRESSED_SIZE = 250 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_FILENAME_LENGTH = 255
OLE_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

MIMETYPES = {
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.odt': 'application/vnd.oasis.opendocument.text',
    '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
    '.odp': 'application/vnd.oasis.opendocument.presentation',
    '.pdf': 'application/pdf',
}

OOXML_DIRECTORIES = {
    '.docx': 'word/',
    '.xlsx': 'xl/',
    '.pptx': 'ppt/',
}


def normalize_filename(filename):
    """Return a safe basename while retaining the user-visible file name."""
    filename = (filename or '').replace('\\', '/').split('/')[-1]
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename).strip()
    if not filename or filename in {'.', '..'}:
        raise ValidationError(_('The uploaded file must have a valid name.'))
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in MIMETYPES:
        raise ValidationError(_('File format is not allowed.'))
    if len(filename) > MAX_FILENAME_LENGTH:
        stem_length = MAX_FILENAME_LENGTH - len(suffix)
        filename = f'{filename[:-len(suffix)][:stem_length]}{suffix}'
    return filename, suffix


def _validate_archive(raw_file, suffix):
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_file))
    except (OSError, zipfile.BadZipFile) as error:
        raise ValidationError(_('The uploaded file is not a valid document container.')) from error

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ValidationError(_('The uploaded document contains too many archive entries.'))
        total_size = 0
        names = set()
        for entry in entries:
            normalized = entry.filename.replace('\\', '/')
            path = PurePosixPath(normalized)
            if (
                normalized.startswith('/')
                or re.match(r'^[a-zA-Z]:/', normalized)
                or path.is_absolute()
                or '..' in path.parts
            ):
                raise ValidationError(_('The uploaded document contains an unsafe archive path.'))
            total_size += entry.file_size
            if total_size > MAX_ARCHIVE_UNCOMPRESSED_SIZE:
                raise ValidationError(_('The uploaded document expands beyond the allowed size.'))
            if entry.file_size and entry.compress_size == 0:
                raise ValidationError(_('The uploaded document has an unsafe compression ratio.'))
            if entry.compress_size and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
                raise ValidationError(_('The uploaded document has an unsafe compression ratio.'))
            names.add(normalized)

        lower_names = {name.lower() for name in names}
        if suffix in OOXML_DIRECTORIES:
            if '[Content_Types].xml' not in names:
                raise ValidationError(_('The uploaded OOXML document has no content type declaration.'))
            expected = OOXML_DIRECTORIES[suffix]
            if not any(name.startswith(expected) for name in names):
                raise ValidationError(_('The uploaded file contents do not match its extension.'))
            if any(name.endswith('/vbaproject.bin') or name == 'vbaproject.bin' for name in lower_names):
                raise ValidationError(_('Macro-enabled documents are not allowed.'))
            content_types = archive.read('[Content_Types].xml').lower()
            if b'macroenabled' in content_types or b'vba' in content_types:
                raise ValidationError(_('Macro-enabled documents are not allowed.'))
        else:
            if 'mimetype' not in names:
                raise ValidationError(_('The uploaded OpenDocument file has no mimetype entry.'))
            try:
                declared_mimetype = archive.read('mimetype').decode('ascii', errors='strict').strip()
            except UnicodeDecodeError as error:
                raise ValidationError(_('The uploaded OpenDocument mimetype is invalid.')) from error
            if declared_mimetype != MIMETYPES[suffix]:
                raise ValidationError(_('The uploaded file contents do not match its extension.'))
            unsafe_parts = ('scripts/', 'basic/', 'script-libraries/')
            if any(any(part in f'/{name.lower()}' for part in unsafe_parts) for name in names):
                raise ValidationError(_('OpenDocument files containing scripts are not allowed.'))
            script_markers = (b'<script:', b'<office:scripts', b'javascript:')
            for name in names:
                if not name.lower().endswith('.xml'):
                    continue
                with archive.open(name) as xml_file:
                    tail = b''
                    while chunk := xml_file.read(64 * 1024):
                        content = (tail + chunk).lower()
                        if any(marker in content for marker in script_markers):
                            raise ValidationError(_('OpenDocument files containing scripts are not allowed.'))
                        tail = content[-32:]


def _validate_pdf(raw_file):
    """Reject spoofed, damaged, encrypted, and empty requested PDF files."""
    if not raw_file.startswith(b'%PDF-'):
        raise ValidationError(_('The uploaded file is not a PDF document.'))
    try:
        reader = pdf.PdfFileReader(io.BytesIO(raw_file), strict=False)
        if reader.isEncrypted:
            raise ValidationError(_('Encrypted requested PDF documents are not supported.'))
        if reader.getNumPages() < 1:
            raise ValidationError(_('The requested PDF document contains no pages.'))
    except ValidationError:
        raise
    except (pdf.DependencyError, pdf.PdfReadError, KeyError, ValueError, TypeError) as error:
        raise ValidationError(_('The requested PDF document is damaged.')) from error


def validate_requested_file(raw_file, filename, max_size=DEFAULT_MAX_REQUESTED_FILE_SIZE):
    """Validate bytes and return normalized attachment metadata."""
    if not isinstance(raw_file, bytes) or not raw_file:
        raise ValidationError(_('The requested document is empty.'))
    normalized_name, suffix = normalize_filename(filename)
    if len(raw_file) > max_size:
        raise ValidationError(_('The requested document exceeds the allowed size.'))
    if suffix in OOXML_DIRECTORIES or suffix in {'.odt', '.ods', '.odp'}:
        _validate_archive(raw_file, suffix)
    elif suffix == '.pdf':
        _validate_pdf(raw_file)
    elif not raw_file.startswith(OLE_SIGNATURE):
        raise ValidationError(_('The uploaded legacy Office file has an invalid signature.'))
    return {
        'filename': normalized_name,
        'mimetype': MIMETYPES[suffix],
        'size': len(raw_file),
        'checksum': hashlib.sha256(raw_file).hexdigest(),
    }
