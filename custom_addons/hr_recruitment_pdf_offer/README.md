# Recruitment PDF Offer

`hr_recruitment_pdf_offer` lets a recruitment user complete AcroForm PDF documents for one applicant before an email template is sent.

## Installation and configuration

1. Install the module after `hr_recruitment`.
2. Create an email template for **Applicant** and enable **Manually complete PDF offer** on its **PDF offer** tab.
3. Upload one or more PDF AcroForms, set their order, and configure every discovered field's label, default source and required flag.
4. Optionally select this template in **Recruitment / Configuration / Stages**. Moving an applicant to that stage schedules a *Prepare PDF offer* activity; it does not send an empty email.

PDFs must be unencrypted AcroForms with at least one text (`/Tx`) field. XFA, checkboxes, choice fields, signatures, ambiguous widgets and unsafe field names are rejected. Store technical field names with only `A-Z`, `a-z`, `0-9`, `_` and `-`.

Use **Prepare and send PDF offer** on one applicant. Edit the prefilled values, choose **Refresh preview**, then move through the documents with **Back** and **Next**. On the final document choose **Done**. Only filled, read-only PDFs are attached to the queued mail; the source PDFs are never added to the template attachments.

## Diagnostics and limits

If a replaced PDF removes a configured field, its mapping is retained but disabled and the template cannot be used until it is corrected. Preview and final rendering re-validate the form structure server-side.

The module relies on the font and appearance dictionary embedded in the original PDF. Verify Cyrillic names and long values in the target browser/PDF reader. A missing Cyrillic font, clipped field, or broken appearance must be corrected in the source PDF; the module deliberately does not replace fonts globally. Read-only AcroForm flags are not cryptographic protection and can be removed with a specialised PDF editor.

The default maximum source PDF size is 10 MiB (`MAX_PDF_SIZE` in the service). Preview bytes are stored on the transient wizard and cleared after a successful queueing; final attachments remain available to the mail queue and chatter.
