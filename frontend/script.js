// Local testing (double-clicking index.html) uses file:// - point it at the
// local Flask server. Once deployed, frontend and backend share the same
// Vercel domain, so a relative path (same origin) is correct there.
const API_BASE = window.location.protocol === "file:" ? "http://localhost:5000" : "";

const fileInput = document.getElementById("file-input");
const processBtn = document.getElementById("process-btn");
const statusMessage = document.getElementById("status-message");

const resultsSection = document.getElementById("results-section");
const warningsBox = document.getElementById("warnings");
const saveBtn = document.getElementById("save-btn");
const saveMessage = document.getElementById("save-message");

let lastReviewReasons = [];

const FIELDS = ["invoice_number", "vendor_name", "invoice_date", "due_date", "total_amount"];

processBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    statusMessage.textContent = "Choose a PDF file first.";
    statusMessage.className = "error-text";
    return;
  }

  statusMessage.textContent = "Processing...";
  statusMessage.className = "";
  processBtn.disabled = true;
  resultsSection.hidden = true;
  saveMessage.textContent = "";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE}/api/process`, {
      method: "POST",
      body: formData
    });
    const data = await response.json();

    if (!response.ok) {
      statusMessage.textContent = data.error || "Something went wrong processing this file.";
      statusMessage.className = "error-text";
      return;
    }

    FIELDS.forEach(field => {
      document.getElementById(`field-${field}`).value = data[field] ?? "";
    });

    lastReviewReasons = data.review_reasons || [];
    if (lastReviewReasons.length > 0) {
      warningsBox.hidden = false;
      warningsBox.innerHTML = "<strong>Flagged for review:</strong><ul>" +
        lastReviewReasons.map(r => `<li>${r}</li>`).join("") + "</ul>";
    } else {
      warningsBox.hidden = true;
      warningsBox.innerHTML = "";
    }

    statusMessage.textContent = "Done. Review the data below.";
    statusMessage.className = "success-text";
    resultsSection.hidden = false;

  } catch (err) {
    statusMessage.textContent = "Could not reach the server. Is the backend running?";
    statusMessage.className = "error-text";
  } finally {
    processBtn.disabled = false;
  }
});

saveBtn.addEventListener("click", async () => {
  saveBtn.disabled = true;
  saveMessage.textContent = "Saving...";
  saveMessage.className = "";

  const invoice = { review_reasons: lastReviewReasons };
  FIELDS.forEach(field => {
    invoice[field] = document.getElementById(`field-${field}`).value;
  });

  try {
    const response = await fetch(`${API_BASE}/api/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(invoice)
    });
    const data = await response.json();

    if (!response.ok) {
      saveMessage.textContent = data.error || "Could not save this invoice.";
      saveMessage.className = "error-text";
      return;
    }

    saveMessage.textContent = `Saved (status: ${data.status}). Record ID: ${data.airtable_record_id}`;
    saveMessage.className = "success-text";

  } catch (err) {
    saveMessage.textContent = "Could not reach the server. Is the backend running?";
    saveMessage.className = "error-text";
  } finally {
    saveBtn.disabled = false;
  }
});
