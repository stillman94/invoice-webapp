import csv

REQUIRED_FIELDS = ['invoice_number', 'vendor_name', 'invoice_date', 'due_date', 'total_amount']


def missing_required_fields(invoice):
    """Which of the 5 required fields came back None/empty from extraction."""
    return [f"Missing required field: {field}" for field in REQUIRED_FIELDS if not invoice.get(field)]


def load_price_list(csv_file_path):
    """Load expected prices into a dict: description -> expected price."""
    price_list = {}
    with open(csv_file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            price_list[row['item_description'].lower()] = float(row['expected_unit_price'])
    return price_list


def validate_invoice_pricing(invoice, price_list, tolerance_percent=5):
    """Flag line items whose unit_price differs too much from the reference price."""
    warnings = []

    for item in invoice.get('line_items', []):
        key = item['description'].lower()
        expected_price = price_list.get(key)

        if expected_price is None:
            warnings.append(f"'{item['description']}' not found in price list - can't verify price")
            continue

        invoiced_price = item['unit_price']
        if invoiced_price is None:
            continue
        percent_diff = abs(invoiced_price - expected_price) / expected_price * 100

        if percent_diff > tolerance_percent:
            warnings.append(
                f"'{item['description']}': invoiced at ${invoiced_price:.2f}, "
                f"expected ${expected_price:.2f} ({percent_diff:.1f}% difference)"
            )

    return warnings


def validate_invoice_math(invoice):
    """Check if invoice math is correct. Mirrors the course pipeline's version -
    tolerates line items missing quantity/unit_price and an optional shipping line."""
    errors = []

    calculated_subtotal = 0
    for i, item in enumerate(invoice.get('line_items', [])):
        if item['quantity'] is not None and item['unit_price'] is not None:
            expected_item_total = item['quantity'] * item['unit_price']
            if abs(expected_item_total - item['total']) > 0.01:
                errors.append(f"Line item {i + 1}: {item['description']} - Math error!")
        calculated_subtotal += item['total'] or 0

    if abs(calculated_subtotal - (invoice.get('subtotal') or 0)) > 0.01:
        errors.append(
            f"Subtotal mismatch: Items sum to ${calculated_subtotal:.2f}, "
            f"invoice says ${invoice.get('subtotal'):.2f}"
        )

    shipping = invoice.get('shipping') or 0
    expected_total = (invoice.get('subtotal') or 0) + shipping + (invoice.get('tax') or 0)
    if abs(expected_total - (invoice.get('total_amount') or 0)) > 0.01:
        errors.append(
            f"Total mismatch: Expected ${expected_total:.2f}, "
            f"invoice says ${invoice.get('total_amount'):.2f}"
        )

    return errors


def lookup_vendor(vendor_name, csv_file):
    """Check if vendor is in the approved list."""
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if vendor_name.lower() in row['vendor_name'].lower():
                return {
                    'found': True,
                    'active': row['active'] == 'TRUE',
                    'id': row['vendor_id'],
                    'terms': row['payment_terms']
                }
    return {'found': False}


def run_all_validations(invoice, vendor_file='vendor-list.csv', price_file='item-price-list.csv'):
    """Run every check the pipeline runs and return a combined list of
    review_reasons (empty if the invoice looks clean)."""
    review_reasons = []

    review_reasons.extend(missing_required_fields(invoice))

    if invoice.get('subtotal') is not None and invoice.get('tax') is not None and invoice.get('total_amount') is not None:
        review_reasons.extend(validate_invoice_math(invoice))

    if invoice.get('line_items'):
        price_list = load_price_list(price_file)
        review_reasons.extend(validate_invoice_pricing(invoice, price_list))

    if not invoice.get('vendor_name'):
        review_reasons.append("Vendor not found in approved vendor list")
    else:
        vendor_check = lookup_vendor(invoice['vendor_name'], vendor_file)
        if not vendor_check['found']:
            review_reasons.append("Vendor not found in approved vendor list")
        elif not vendor_check['active']:
            review_reasons.append("Vendor is marked inactive in approved vendor list")

    return review_reasons
