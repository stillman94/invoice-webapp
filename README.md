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
├── backend/
│   ├── app.py              # Flask server (/api/process, /api/save)
│   ├── pdf_processor.py    # PDF extraction (reused from Lesson 2.2)
│   ├── validation.py       # Math/price/vendor checks (reused from Lesson 2.2)
│   ├── airtable_client.py  # Airtable read/write, dedupe by Invoice Number + Vendor
│   ├── vendor-list.csv
│   ├── item-price-list.csv
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Running it locally

```powershell
cd backend
pip install -r requirements.txt
python app.py
```

Server starts at `http://localhost:5000`. Then open `frontend/index.html` directly in a browser.

## Environment variables

Uses the same shared `.env` as the rest of this project (`C:\Users\ArabS\.env`), loaded via `load_dotenv(os.path.expanduser("~/.env"))`. Needs:

- `AIRTABLE_TOKEN`
- `TEST_BASE_ID` (used by default)
- `BASE_ID` (production base - only used if `PIPELINE_ENV=production` is set)

No separate `.env` file needed inside this folder.

## Notes

- Defaults to the **test** Airtable base for safety. Set `PIPELINE_ENV=production` as an environment variable before running to target the real base.
- Max upload size: 5MB. Only `.pdf` files are accepted.
- Logs to `backend/logs/webapp_YYYY-MM-DD.log`.
