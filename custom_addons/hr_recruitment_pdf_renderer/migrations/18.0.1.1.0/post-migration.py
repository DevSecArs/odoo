def migrate(cr, version):
    """Keep existing PDF configuration and persistent drafts unchanged."""
    cr.execute("""
        UPDATE mail_template_offer_pdf_document
           SET document_type = 'fillable_pdf'
         WHERE document_type IS NULL
    """)
    cr.execute("""
        UPDATE hr_pdf_document_draft_document
           SET document_type = 'fillable_pdf'
         WHERE document_type IS NULL
    """)
    cr.execute("""
        ALTER TABLE mail_template_offer_pdf_document
        ALTER COLUMN pdf_filename DROP NOT NULL
    """)
    cr.execute("""
        ALTER TABLE hr_pdf_document_draft_document
        ALTER COLUMN value_map DROP NOT NULL
    """)
