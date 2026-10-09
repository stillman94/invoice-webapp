import re
import json
from datetime import datetime
import pdfplumber


def clean_text(text):
    """Strip leftover formatting tags (e.g. <b>...</b>) from the text layer."""
    return re.sub(r'</?b>', '', text)


def extract_field(text, label_patterns, value_pattern=r'\$?([\d,]+\.\d{2})'):
    """Find a labeled value like 'Subtotal: $2,615.00' and return the
    matched value string, or None if none of the label patterns are found.

    label_patterns can be a single pattern or a list of alternatives -
    different vendor templates use different labels for the same field
    (e.g. 'Invoice Number:' vs 'Invoice #:'), so we try each in order and
    use the first one that matches.
    """
    if isinstance(label_patterns, str):
        label_patterns = [label_patterns]

    for label_pattern in label_patterns:
        match = re.search(label_pattern + r'\s*' + value_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def normalize_date(date_str):
    """Convert MM/DD/YYYY to YYYY-MM-DD."""
    return datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')


def parse_money(value_str):
    """Turn '$2,824.20' or '2824.20' into a float."""
    if not value_str:
        return None
    return float(value_str.replace('$', '').replace(',', '').strip())


def extract_notes(text):
    """Pull a short notes line off the invoice. Prefers an explicit
    'Payment terms: ...' line; falls back to whatever immediately follows
    a 'Notes:' / 'Special Notes:' header, since not every vendor template
    states payment terms in the notes section."""
    payment_terms_match = re.search(r'Payment\s*terms:.*', text, re.IGNORECASE)
    if payment_terms_match:
        return payment_terms_match.group(0).strip()

    notes_header_match = re.search(
        r'(?:(?:Special\s+)?Notes|IMPORTANT\s+NOTICE):?\s*\n\s*(.+)', text, re.IGNORECASE
    )
    if notes_header_match:
        # Some templates put a literal '<br/>' in one raw line instead of a
        # real line break - keep only the headline sentence before it.
        return notes_header_match.group(1).split('<br')[0].strip()

    return None


_ACRONYM_SUFFIXES = {'Llc': 'LLC', 'Llp': 'LLP', 'Lp': 'LP', 'Pc': 'PC'}


def normalize_vendor_name(name):
    """Some vendor templates print the company name in all-caps, which
    reads like shouting once it lands in Airtable - title-case it when the
    source was all-caps, and strip a trailing period some templates put
    after a suffix like 'Inc.'. Title-casing alone turns 'LLC' into 'Llc',
    so re-uppercase known corporate-suffix acronyms afterward."""
    if name.isupper():
        words = name.title().split(' ')
        name = ' '.join(_ACRONYM_SUFFIXES.get(w, w) for w in words)
    return name.rstrip('.')


_KNOWN_TAGS = re.compile(r'</?b>|<font[^>]*>|</font>|<br\s*/?>', re.IGNORECASE)


def detect_text_corruption(raw_text):
    """Flag PDFs whose text layer shows signs of rendering corruption.

    Real invoice text should never contain literal formatting tags -
    if it does, something upstream (usually two overlapping table cells)
    scrambled the text layer, and any field we 'extracted' from that
    region can't be trusted. We strip out well-formed tags we already
    know how to tolerate (<b>, <font>, <br/>) and treat anything else
    that still looks tag-shaped as a corruption signal, since that only
    happens when markup characters get interleaved with surrounding text.

    Returns a list of warning strings (empty if nothing looks wrong) -
    same shape as validate_invoice_pricing()/lookup_vendor(), so this
    slots straight into the pipeline's existing review_reasons list.
    """
    remaining = _KNOWN_TAGS.sub('', raw_text)
    stray_tags = re.findall(r'<[^<>]{0,40}>', remaining)

    if stray_tags:
        return [
            f"Possible PDF text corruption detected (malformed tag fragment: "
            f"{stray_tags[0]!r}) - extracted fields should be manually verified"
        ]
    return []


def looks_like_a_header_row(row):
    """'Description' is the one column every vendor template's real
    line-items table has - used to tell a genuine header row apart from
    a bordered info/notice box pdfplumber also detected as a 'table', and
    from a page-2 continuation table that has no header row at all."""
    return 'description' in [(c or '').strip().lower() for c in row]


def parse_line_item_row(header, row):
    """Turn one pdfplumber table row into our line_items shape, using the
    given header to know which column is which. Handles both the
    2-column (Description, Amount) and 4/5/6-column (..., Qty, Unit
    Price, Total) vendor templates - extra columns (Item #, SKU) are
    simply ignored."""
    row_dict = dict(zip(header, row))
    description = (row_dict.get('description') or '').strip()

    amount_str = row_dict.get('total') or row_dict.get('amount') or row_dict.get('line total')
    total = parse_money(amount_str)

    quantity_str = row_dict.get('qty') or row_dict.get('quantity')
    quantity = int(quantity_str) if quantity_str and quantity_str.strip() else None

    unit_price = parse_money(row_dict.get('unit price'))

    return {
        'description': description,
        'quantity': quantity,
        'unit_price': unit_price,
        'total': total
    }


def extract_line_items(pages_data):
    """Collect line items across every page. Most invoices repeat the
    line-items table's header on every page, but a long invoice that
    spans pages (e.g. 20 items over 2 pages) may only print the header
    once on page 1 and continue with bare data rows on page 2 - so once
    we've seen a real header, a header-less table with the SAME number
    of columns is treated as more rows of that table. The column-count
    check matters: a page can also have an unrelated 1-column info/notice
    box after the real items table, which must NOT be swept in as more
    line items just because a header was seen earlier."""
    items = []
    current_header = None

    for page in pages_data:
        for table in page['tables']:
            header_row = [(c or '').strip().lower() for c in table[0]]

            if looks_like_a_header_row(table[0]):
                current_header = header_row
                data_rows = table[1:]
            elif current_header and len(table[0]) == len(current_header):
                data_rows = table
            else:
                continue  # not a line-items table, or an unrelated table

            items.extend(parse_line_item_row(current_header, row) for row in data_rows)

    return items


def extract_invoice_fields(pages_data):
    """Map raw pdfplumber output to the same JSON shape used by
    sample-invoice-data.json: invoice_number, vendor_name, invoice_date,
    due_date, subtotal, tax, total_amount, line_items, notes."""
    raw_text = "\n".join(page['text'] for page in pages_data)
    full_text = clean_text(raw_text)
    first_line = full_text.strip().split('\n')[0].strip()
    # Some templates put the company name and the "INVOICE" title side by
    # side in the same header row, so they land on one text line together.
    vendor_name = re.sub(r'\s*INVOICE\s*$', '', first_line, flags=re.IGNORECASE).strip()
    vendor_name = normalize_vendor_name(vendor_name)

    invoice_number = extract_field(
        full_text, [r'Invoice\s*Number:', r'Invoice\s*#:?'], r'([A-Z0-9-]+)'
    )
    invoice_date_raw = extract_field(
        full_text, [r'Invoice\s*Date:', r'(?<!Due )\bDate:'], r'(\d{1,2}/\d{1,2}/\d{4})'
    )
    due_date_raw = extract_field(
        full_text, [r'Due\s*Date:', r'\bDue:'], r'(\d{1,2}/\d{1,2}/\d{4})'
    )
    subtotal = extract_field(full_text, r'Subtotal:')
    shipping = extract_field(full_text, r'\bShipping:')
    tax = extract_field(full_text, r'Tax\s*(?:\([^)]*\))?:')
    total_amount = extract_field(full_text, [r'\bTotal\s*(?:Due)?:', r'Amount\s*Due:'])

    line_items = extract_line_items(pages_data)

    return {
        'invoice_number': invoice_number,
        'vendor_name': vendor_name,
        'invoice_date': normalize_date(invoice_date_raw) if invoice_date_raw else None,
        'due_date': normalize_date(due_date_raw) if due_date_raw else None,
        'subtotal': parse_money(subtotal),
        'shipping': parse_money(shipping),
        'tax': parse_money(tax),
        'total_amount': parse_money(total_amount),
        'line_items': line_items,
        'notes': extract_notes(full_text),
        'extraction_warnings': detect_text_corruption(raw_text)
    }


def extract_raw_pdf_data(pdf_path):
    """Open a PDF and return what pdfplumber sees on each page: the raw
    text and any tables it detects. No field-mapping yet - this is just
    'what's in here' before we go hunting for specific values."""
    pages_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            pages_data.append({
                "page_number": page_num,
                "text": page.extract_text(),
                "tables": page.extract_tables()
            })

    return pages_data

if __name__ == "__main__":
    pdf_path = "test_data/invoice-004-global-shipping.pdf"
    pages = extract_raw_pdf_data(pdf_path)

    invoice_data = extract_invoice_fields(pages)

    print("=" * 60)
    print("EXTRACTED INVOICE DATA")
    print("=" * 60)
    print(json.dumps(invoice_data, indent=2))
