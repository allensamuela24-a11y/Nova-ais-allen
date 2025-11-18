# ~/novaais/gmail_poller.py
import time, json, requests, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64, email

ROOT = Path(__file__).parent
TOK = ROOT / "novaais_core" / "token.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.modify','https://www.googleapis.com/auth/gmail.readonly']

if not TOK.exists():
    print("token.json missing at", TOK)
    sys.exit(1)

creds = Credentials.from_authorized_user_file(str(TOK), SCOPES)
svc = build('gmail','v1',credentials=creds)
APP_URL = "http://127.0.0.1:8080/reply"   # If deployed, change to your Cloud Run URL

POLL_INTERVAL = 5   # seconds

def get_unread_message_ids():
    try:
        resp = svc.users().messages().list(userId="me", q="is:unread", maxResults=10).execute()
        return [m['id'] for m in resp.get('messages',[])]
    except HttpError as e:
        print("Gmail API error listing messages:", e)
        return []

def fetch_full_message(mid):
    m = svc.users().messages().get(userId="me", id=mid, format="full").execute()
    payload = m.get('payload',{})
    headers = {h['name']: h['value'] for h in payload.get('headers',[])}
    subject = headers.get('Subject','(no subject)')
    from_header = headers.get('From','')
    # get body snippet / text
    body = m.get('snippet','')
    # if you want the body text more accurately, attempt to decode parts:
    if payload.get('parts'):
        for part in payload['parts']:
            if part.get('mimeType','').startswith('text/plain'):
                data = part.get('body',{}).get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                    break
    return {"id": mid, "subject": subject, "from": from_header, "body": body, "threadId": m.get('threadId')}

def mark_read(mid):
    try:
        svc.users().messages().modify(userId="me", id=mid, body={"removeLabelIds":["UNREAD"]}).execute()
    except Exception as e:
        print("Failed to mark read:", e)

print("Starting poller. Press Ctrl+C to stop.")
try:
    while True:
        ids = get_unread_message_ids()
        if ids:
            print("Found unread:", ids)
        for mid in ids:
            try:
                msg = fetch_full_message(mid)
                print("Processing:", msg['id'], msg['from'], msg['subject'])
                payload = {
                    "from_email": msg['from'],
                    "subject": msg['subject'],
                    "body": msg['body'],
                    "use_templates": True
                }
                # call local app (it will send/reply via gmail_auth.send_email)
                r = requests.post(APP_URL, json=payload, timeout=30)
                print("POST /reply =>", r.status_code, r.text[:400])
                # mark message read to avoid reprocessing
                mark_read(mid)
            except Exception as e:
                print("Error processing message", mid, e)
        time.sleep(POLL_INTERVAL)
except KeyboardInterrupt:
    print("Stopping poller.")
