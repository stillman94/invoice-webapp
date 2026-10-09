import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env"))

# Defaults to the test base for safety - set PIPELINE_ENV=production to target real data.
PIPELINE_ENV = os.getenv("PIPELINE_ENV", "test")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("BASE_ID") if PIPELINE_ENV == "production" else os.getenv("TEST_BASE_ID")
TABLE_NAME = "Invoices"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


class AirtableAuthError(Exception):
    """Airtable rejected our credentials (401/403)."""


def build_line_items_text(invoice):
    """Build a human-readable summary of line items for the Notes field."""
    text = "Line Items:\n"
    for item in invoice.get('line_items', []):
        text += f"- {item['description']}: ${item['total']}\n"
    return text


def transform_for_airtable(invoice, status="Received", review_reasons=None):
    """Transform invoice to Airtable format."""
    notes = build_line_items_text(invoice)
    if invoice.get('notes'):
        notes += f"\n{invoice['notes']}"

    return {
        "Invoice Number": invoice['invoice_number'],
        "Vendor Name": invoice['vendor_name'],
        "Invoice Date": invoice['invoice_date'],
        "Due Date": invoice['due_date'],
        "Total Amount": invoice['total_amount'],
        "Invoice Status": status,
        "Additional Notes": notes,
        # Always include this key, even when empty - Airtable's PATCH is a
        # partial update, so omitting it would keep a stale flag from an
        # earlier run.
        "Flagged for Review": "\n".join(f"- {reason}" for reason in review_reasons) if review_reasons else ""
    }


def find_existing_record(invoice_number, vendor_name):
    """Look up an existing record by Invoice Number + Vendor Name together,
    so re-saving an edited invoice updates it instead of creating a duplicate."""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    safe_invoice_number = invoice_number.replace('"', '\\"')
    safe_vendor_name = (vendor_name or "").replace('"', '\\"')
    params = {
        "filterByFormula": (
            f'AND({{Invoice Number}} = "{safe_invoice_number}", '
            f'{{Vendor Name}} = "{safe_vendor_name}")'
        )
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    if response.status_code in (401, 403):
        raise AirtableAuthError(
            f"Airtable rejected credentials ({response.status_code}) while looking up "
            f"{invoice_number!r} / {vendor_name!r}"
        )
    response.raise_for_status()
    records = response.json().get("records", [])
    return records[0]["id"] if records else None


def create_airtable_record(data):
    """Create or update the Airtable record for this invoice, retrying on
    transient (5xx/network) failures. Returns (success, record_id)."""
    try:
        existing_id = find_existing_record(data["Invoice Number"], data.get("Vendor Name"))
    except requests.exceptions.RequestException as e:
        return False, None

    if existing_id:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}/{existing_id}"
        method = "PATCH"
    else:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
        method = "POST"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"fields": data, "typecast": True}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, headers=headers, json=payload, timeout=10)
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            return False, None

        if response.status_code in (401, 403):
            raise AirtableAuthError(f"Airtable rejected credentials ({response.status_code})")

        if response.status_code == 200:
            return True, response.json().get("id", existing_id)

        if response.status_code >= 500 and attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        return False, None

    return False, None
