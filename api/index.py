import os
import tempfile
import logging
from datetime import date

from flask import Flask, request, jsonify
from flask_cors import CORS

from pdf_processor import extract_raw_pdf_data, extract_invoice_fields
from validation import run_all_validations
from airtable_client import transform_for_airtable, create_airtable_record, AirtableAuthError

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_BYTES

VENDOR_FILE = os.path.join(os.path.dirname(__file__), 'vendor-list.csv')
PRICE_FILE = os.path.join(os.path.dirname(__file__), 'item-price-list.csv')


# Serverless functions (Vercel) can't write to their own project folder -
# only to the system temp directory, which is also writable in local dev.
LOG_DIR = os.path.join(tempfile.gettempdir(), "invoice_webapp_logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"webapp_{date.today().isoformat()}.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("invoice_webapp")


@app.errorhandler(413)
def handle_file_too_large(e):
    return jsonify({"error": "File is too large - max size is 5MB"}), 413


@app.route('/api/process', methods=['POST'])
def process_invoice():
    """Accept a PDF upload, extract invoice data, and return it (plus any
    validation warnings) for the user to review before saving."""
    if 'file' not in request.files:
        return jsonify({"error": "No file was uploaded"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No file was selected"}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are supported"}), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        pages = extract_raw_pdf_data(tmp_path)
        invoice = extract_invoice_fields(pages)

        extraction_warnings = invoice.pop('extraction_warnings', [])
        review_reasons = extraction_warnings + run_all_validations(invoice, VENDOR_FILE, PRICE_FILE)

        invoice['review_reasons'] = review_reasons
        logger.info(f"{file.filename}: processed, {len(review_reasons)} warning(s)")
        return jsonify(invoice), 200

    except Exception as e:
        logger.error(f"{file.filename}: extraction failed - {e}")
        return jsonify({"error": f"Could not read this PDF: {e}"}), 422

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.route('/api/save', methods=['POST'])
def save_invoice():
    """Accept (possibly user-edited) invoice data and write it to Airtable."""
    invoice = request.get_json(silent=True)
    if not invoice:
        return jsonify({"error": "No invoice data received"}), 400

    required = ['invoice_number', 'vendor_name', 'invoice_date', 'due_date', 'total_amount']
    missing = [f for f in required if not invoice.get(f)]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    review_reasons = invoice.get('review_reasons') or []
    status = "Needs Review" if review_reasons else "Received"

    try:
        airtable_data = transform_for_airtable(invoice, status=status, review_reasons=review_reasons)
        success, record_id = create_airtable_record(airtable_data)
    except AirtableAuthError as e:
        logger.critical(f"Airtable auth failure: {e}")
        return jsonify({"error": "Airtable rejected our credentials - contact the automation owner"}), 502

    if not success:
        logger.error(f"{invoice.get('invoice_number')}: Airtable write failed")
        return jsonify({"error": "Could not reach Airtable after retries - try again shortly"}), 502

    logger.info(f"{invoice.get('invoice_number')}: saved (status={status})")
    return jsonify({"success": True, "airtable_record_id": record_id, "status": status}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
