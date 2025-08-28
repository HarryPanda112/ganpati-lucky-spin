from flask import Flask, render_template, request, jsonify
import datetime, random, gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Timezone & Expiry
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
GLOBAL_EXPIRY = datetime.datetime(2025, 9, 30, 23, 59, 59, tzinfo=IST)
PRIZES = ["Smart Watch","Bluetooth Speaker","Earphones",
          "AirPods","Analog Watch","Digital Watch"]

# Google Sheets IDs
CODES_SHEET_ID = "1ZpoeQ2eEJSd7yDZT2ObC5hqiEKfn0bhEa_GAd9kfiSM"
ATTEMPTS_SHEET_ID = "1ZhLeSN5rOwA1_NIWxisrZ-xMJKab3ihwisvvYxuV7Zw"

# Authenticate with service account JSON
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]
import json, os

creds_json = os.environ.get("GOOGLE_CREDENTIALS")
if creds_json:
    creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scope)
else:
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)


client = gspread.authorize(creds)

# Worksheets
codes_sheet = client.open_by_key(CODES_SHEET_ID).worksheet("Codes")
attempts_sheet = client.open_by_key(ATTEMPTS_SHEET_ID).worksheet("Attempts")

def parse_expiry(val):
    if not val:
        return GLOBAL_EXPIRY
    try:
        d = datetime.datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
        return datetime.datetime.combine(d, datetime.time(23, 59, 59), tzinfo=IST)
    except:
        return GLOBAL_EXPIRY

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/redeem", methods=["POST"])
def redeem():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()
    if not name or not code:
        return jsonify(ok=False, reason="missing", message="Enter name and code.")

    # Validate code
    codes = codes_sheet.get_all_records()
    code_row = next(((i, r) for i, r in enumerate(codes, start=2) 
                     if str(r.get("Code", "")).upper() == code), None)

    if not code_row:
        log_attempt(name, code, "INVALID", "")
        return jsonify(ok=False, reason="invalid", message="❌ Invalid Code.")

    row_idx, row = code_row
    status = str(row.get("Status", "")).strip().lower()
    expiry = parse_expiry(row.get("Expiry", ""))
    now = datetime.datetime.now(IST)

    if now > expiry:
        log_attempt(name, code, "EXPIRED", "")
        return jsonify(ok=False, reason="expired", message="⏰ Code expired.")

    if status == "used":
        log_attempt(name, code, "ALREADY_USED", "")
        return jsonify(ok=False, reason="used", message="⚠️ Code already used.")

    # Assign random prize
    prize = random.choice(PRIZES)

    # Mark code used (column 2 = Status)
    codes_sheet.update_cell(row_idx, 2, "Used")

    # Log success
    log_attempt(name, code, "SUCCESS", prize)

    return jsonify(ok=True, prize=prize, message=f"🎉 You won: {prize}")

def log_attempt(name, code, result, prize):
    """Append attempt with increasing attempt count."""
    timestamp = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")
    past_attempts = attempts_sheet.get_all_records()
    attempt_num = sum(1 for r in past_attempts 
                      if r.get("Name","").lower()==name.lower() and r.get("Code","").upper()==code.upper()) + 1
    attempts_sheet.append_row([timestamp, name, code, result, prize or "", attempt_num])

if __name__ == "__main__":
    app.run(debug=True)
