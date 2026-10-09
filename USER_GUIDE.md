# Invoice Upload Tool - User Guide

## What This Does

Upload an invoice PDF, see the data it pulled out (invoice number, vendor, dates, amount), fix anything that looks wrong, and save it straight to Airtable. No folder access or technical setup needed.

## How to Use

1. Open: **https://invoice-webapp-phi.vercel.app**
2. Click "Choose File" and select your invoice PDF
3. Click "Process Invoice"
4. Review the extracted fields below - if anything's wrong (a misread date, a typo'd vendor name), just click into the field and fix it
5. If you see a yellow "Flagged for review" box, read it - it's telling you specifically what looks off (a math error, a vendor not on the approved list, a price that doesn't match the catalog, etc.)
6. Click "Save to Airtable"
7. You'll see a confirmation with the Airtable record ID - check Airtable to see your invoice

## Status Meaning

Every invoice you save gets a status in Airtable:

- **Received** - everything checked out clean
- **Needs Review** - something looked off and is noted in the "Flagged for Review" field on that record. This doesn't mean the invoice is rejected - it just means a human should double check it before it's approved for payment.

## Troubleshooting

- **"Only PDF files are supported"** - you uploaded something that isn't a PDF. Re-save or re-export the file as a PDF and try again.
- **"File is too large - max size is 5MB"** - the PDF is over the size limit. Try re-saving/compressing it, or contact [your name/email] if this keeps happening.
- **"Could not reach the server"** - the tool may be temporarily down. Wait a minute and try again; if it keeps happening, contact [your name/email].
- **Extraction looks wrong or incomplete (blank fields, garbled vendor name)** - this usually means the PDF's underlying text is a scanned image or slightly corrupted. Just fill in the correct values by hand before saving - nothing is saved until you click "Save to Airtable."
- **Uploaded the same invoice twice by accident?** - no problem. The tool recognizes it by Invoice Number + Vendor and updates the existing record instead of creating a duplicate.

## Supported Invoice Formats

Works best with:

- Standard invoices with a clear invoice number and dates in MM/DD/YYYY format
- Dollar amounts with a $ symbol

May need manual correction for:

- Handwritten invoices
- Scanned images (low-quality or no text layer)
- Unusual or heavily custom invoice layouts

## Questions?

Contact [your name/email] - built and maintains this tool.
