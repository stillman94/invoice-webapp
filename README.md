# Invoice Upload Web App

A self-service web tool: upload a PDF invoice, review the extracted data, and save it to Airtable - no terminal or folder access required.

## What it does

1. Upload a PDF invoice through the browser
2. Backend extracts invoice number, vendor, dates, amount, and line items
3. Extracted data is checked against the same rules as the main pipeline (math, approved vendor list, price catalog)
4. You review (and can edit) the data before anything is saved
5. Click "Save to Airtable" - record is created or updated (Status: `Received` or `Needs Review`)

## Project structure

```
invoice-upload-webapp/
├── api/
│   ├── index.py             # Flask server (/api/process, /api/save) - Vercel auto-detects this as a serverless function
│   ├── pdf_processor.py     # PDF extraction (reused from Lesson 2.2)
│   ├── validation.py        # Math/price/vendor checks (reused from Lesson 2.2)
│   ├── airtable_client.py   # Airtable read/write, dedupe by Invoice Number + Vendor
│   ├── vendor-list.csv
│   └── item-price-list.csv
├── public/                  # Vercel auto-serves these as static files
│   ├── index.html
│   ├── style.css
│   └── script.js
└── requirements.txt
```

This layout (not `backend/`/`frontend/`) is required by Vercel's zero-config Python support - a Flask app at `api/index.py` is automatically deployed as a serverless function, and anything in `public/` is automatically served as static files. No `vercel.json` needed.

## Running it locally

```powershell
cd api
pip install -r ../requirements.txt
python index.py
```

Server starts at `http://localhost:5000`. Then open `public/index.html` directly in a browser.

## Environment variables

Uses the same shared `.env` as the rest of this project (`C:\Users\ArabS\.env`), loaded via `load_dotenv(os.path.expanduser("~/.env"))`. Needs:

- `AIRTABLE_TOKEN`
- `TEST_BASE_ID` (used by default)
- `BASE_ID` (production base - only used if `PIPELINE_ENV=production` is set)

No separate `.env` file needed inside this folder.

## Notes

- Defaults to the **test** Airtable base for safety. Set `PIPELINE_ENV=production` as an environment variable before running to target the real base.
- Max upload size: 5MB. Only `.pdf` files are accepted.
- Logs to the system temp directory (`invoice_webapp_logs/webapp_YYYY-MM-DD.log`) - required since Vercel's serverless functions can't write to their own project folder.
