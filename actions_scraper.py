"""
actions_scraper.py
────────────────────
GitHub Actions ke andar chalne wala entry point.
Laptop wale app.py ke run_scraper() jaisa hi kaam karta hai, bas:
  - Accounts TCI_ACCOUNTS secret (JSON) se aate hain (Flask/tci_data.json nahi)
  - From/To date workflow_dispatch inputs se aate hain (agar diye hain),
    warna default pichle mahine ki range
  - Result seedha Firebase Realtime Database mein PATCH hota hai —
    sirf trip_details/last_updated/account_names update hote hain,
    vehicle_info (jo mobile app se manually maintain hota hai) touch nahi hota
"""
import os
import json
import datetime
import urllib.request
import urllib.error

from scraper import scrape_all_accounts

# Fixed order — Manish, Suresh, Subhita, Tushar, Bhojraj
ACCOUNT_ORDER = ["MA", "SA", "SB", "TC", "BJ"]


def get_date_range():
    """Pichle mahine ki date range (default, agar custom date na di ho)"""
    today = datetime.date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - datetime.timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.strftime("%d-%b-%Y"), last_prev.strftime("%d-%b-%Y")


def get_id_token(api_key, email, password):
    """Firebase Auth se login karke idToken leta hai (Realtime DB likhne ke liye)"""
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    body = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["idToken"]


def push_update(db_url, id_token, payload):
    """PATCH — sirf diye gaye keys update karta hai, baaki data (jaise
    vehicle_info) ko bina chhede chhod deta hai."""
    url = f"{db_url}/tci_data.json?auth={id_token}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="PATCH",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def main():
    accounts = json.loads(os.environ["TCI_ACCOUNTS"])

    # Fixed order mein arrange karo
    ordered_accounts = {}
    for key in ACCOUNT_ORDER:
        if key in accounts:
            ordered_accounts[key] = accounts[key]
    for key, val in accounts.items():
        if key not in ordered_accounts:
            ordered_accounts[key] = val

    from_date = (os.environ.get("FROM_DATE") or "").strip()
    to_date = (os.environ.get("TO_DATE") or "").strip()
    if not from_date or not to_date:
        from_date, to_date = get_date_range()

    print(f"Scraping from {from_date} to {to_date}")
    results = scrape_all_accounts(ordered_accounts, from_date, to_date)
    ordered_results = {k: results.get(k, []) for k in ordered_accounts}
    account_names = {k: v.get("name") for k, v in ordered_accounts.items()}

    payload = {
        "last_updated": datetime.datetime.now().strftime("%d-%b-%Y %H:%M"),
        "trip_details": ordered_results,
        "account_names": account_names,
    }

    api_key = os.environ["FIREBASE_API_KEY"]
    db_url = os.environ["FIREBASE_DB_URL"]
    email = os.environ["FIREBASE_EMAIL"]
    password = os.environ["FIREBASE_PASSWORD"]

    print("Firebase mein login ho raha hai...")
    id_token = get_id_token(api_key, email, password)

    print("Firebase update ho raha hai...")
    push_update(db_url, id_token, payload)

    print("✅ Firebase update ho gaya — mobile app mein ab naya data dikhega.")


if __name__ == "__main__":
    main()
