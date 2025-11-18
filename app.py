# app.py
# Nova AIS – FINAL Production Backend (Cloud Run Ready)
# Copy-paste this file to replace your existing app.py

import re
import os
import json
import time
import random
import sqlite3
import logging
from pathlib import Path
import sys
import traceback
from typing import Optional, Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -----------------------
# Gemini 2.5 Flash client w/ retry & tone safety
# -----------------------
try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

def gemini_generate_text(
        prompt: str,
        model: str = "gemini-2.5-flash",
        retries: int = 4,
        backoff_base: float = 0.6
):
    """
    Robust Gemini call with retries/backoff.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or genai is None:
        return "Gemini API key missing."

    client = genai.Client(api_key=api_key)

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[prompt],
                config=types.GenerateContentConfig(response_modalities=["TEXT"])
            )
            return resp.text

        except Exception as e:
            msg = str(e)
            last_exc = e

            transient = (
                "503" in msg
                or "UNAVAILABLE" in msg
                or "rateLimitExceeded" in msg
                or "overloaded" in msg.lower()
            )

            if not transient:
                return f"Gemini error: {e}"

            sleep_sec = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
            logging.warning(
                f"Gemini transient error (attempt {attempt}/{retries}): {msg} — retrying in {sleep_sec:.2f}s"
            )
            time.sleep(sleep_sec)

    return f"Gemini error after retries: {last_exc}"

def gemini_generate(prompt: str):
    return gemini_generate_text(prompt)

# -----------------------
# Firestore
# -----------------------
try:
    from google.cloud import firestore
except Exception:
    firestore = None

# -----------------------
# Gmail API helper imports (for building service if token.json present)
# -----------------------
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except Exception:
    Credentials = None
    Request = None
    build = None

# -----------------------
# Import template logic (gmail_auth) and txn DB helper
# -----------------------
ROOT = Path(__file__).parent
CORE = ROOT / "novaais_core"
sys.path.insert(0, str(CORE))

try:
    import gmail_auth
except Exception as e:
    gmail_auth = None
    logging.warning(f"Could not import gmail_auth: {e}")

try:
    import transaction_db_setup as txn_db
except Exception as e:
    txn_db = None
    logging.warning(f"Could not import transaction_db_setup: {e}")

# -----------------------
# SQLite DB bootstrap (keeps working copy under novaais_core)
# -----------------------
DB_PATH = CORE / "transactions.db"

try:
    if not DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT,
                email TEXT,
                merchant TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                date TEXT
            )
        """)

        # Seed TXN001
        c.execute("""
            INSERT INTO transactions (transaction_id, email, merchant, amount, currency, status, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("TXN001", "allen@example.com", "NovaStore", 59.99, "EUR", "Paid", "2025-06-06"))

        conn.commit()
        conn.close()

        logging.info("Seeded SQLite TXN001.")

except Exception as e:
    logging.warning(f"SQLite DB setup error: {e}")

# -----------------------
# Firestore bootstrap
# -----------------------
USE_FIRESTORE = os.environ.get("USE_FIRESTORE", "true").lower() in ("1", "true", "yes")
db = None

if USE_FIRESTORE and firestore is not None:
    try:
        db = firestore.Client()
    except Exception as e:
        logging.warning(f"Firestore init failed: {e}")
        db = None

# Seed Firestore transaction (if Firestore available)
try:
    if db:
        q = db.collection("transactions") \
              .where("transaction_id", "==", "TXN001") \
              .limit(1).stream()

        exists = any(True for _ in q)

        if not exists:
            db.collection("transactions").add({
                "transaction_id": "TXN001",
                "email": "allen@example.com",
                "merchant": "NovaStore",
                "amount": 59.99,
                "currency": "EUR",
                "status": "Paid",
                "date": "2025-06-06",
                "seeded_by": "startup",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            logging.info("Seeded TXN001 in Firestore.")
except Exception as e:
    logging.warning(f"Firestore seeding error: {e}")

# -----------------------
# Gmail service builder (uses token.json in novaais_core)
# -----------------------
GMAIL_TOKEN_PATH = CORE / "token.json"
GMAIL_SCOPES = getattr(gmail_auth, "SCOPES", ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']) if gmail_auth else ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

_gmail_service = None
def build_gmail_service():
    global _gmail_service
    if Credentials is None or build is None:
        logging.warning("google oauth libraries not available; Gmail API disabled.")
        return None
    try:
        if not GMAIL_TOKEN_PATH.exists():
            logging.warning("token.json not found at %s - Gmail API unavailable.", str(GMAIL_TOKEN_PATH))
            return None
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)
        if creds and not getattr(creds, "valid", False) and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.warning("Failed to refresh Gmail credentials: %s", e)
                return None
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        logging.warning("Failed to build Gmail service: %s", e)
        return None

def get_gmail_service():
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = build_gmail_service()
    return _gmail_service

# -----------------------
# FastAPI init
# -----------------------
app = FastAPI(title="Nova AIS API")

# -----------------------
# Request Models
# -----------------------
class EmailIn(BaseModel):
    subject: Optional[str] = None
    from_email: str
    body: str
    message_id: Optional[str] = None

class VerifyIn(BaseModel):
    transaction_id: str
    sender_email: str

class ReplyIn(BaseModel):
    subject: Optional[str] = None
    from_email: str
    body: str
    use_templates: Optional[bool] = True

# -----------------------
# Logging
# -----------------------
LOG_FILE = "local_novaais_logs.jsonl"

def log_action(doc: Dict[str, Any]):
    doc["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        if db:
            db.collection("nova_ais_logs").add(doc)
            return
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(doc) + "\n")
    except Exception as e:
        logging.error(f"Local log write failed: {e}")

# -----------------------
# Helper: SQLite table columns
# -----------------------
def sqlite_table_columns(conn: sqlite3.Connection, table_name: str):
    """Return a set of column names for a SQLite table (safe)."""
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = [row[1] for row in cur.fetchall()]  # row[1] is column name
        return set(cols)
    except Exception:
        return set()

# -----------------------
# HEALTH
# -----------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "use_firestore": bool(db),
        "gmail_api": bool(get_gmail_service()),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")) and genai is not None
    }

# -----------------------
# CLASSIFY
# -----------------------
@app.post("/classify")
async def classify_email(payload: EmailIn):
    try:
        body = payload.body or ""
        sender = payload.from_email

        # Templates first
        if gmail_auth and hasattr(gmail_auth, "match_template"):
            try:
                tmpl, action, txn = gmail_auth.match_template(body, sender)
                if tmpl:
                    result = {"template_response": tmpl, "action": action, "transaction_data": txn}
                    log_action({"type": "classify", "from": sender, "subject": payload.subject, "result": result})
                    return result
            except Exception:
                pass

        # Gemini fallback
        prompt = f"""
Classify this email into one of:
Refund, Fraud, GDPR, PaymentIssue, Other.

Email:
{body}
"""
        classification = gemini_generate(prompt)
        result = {"classification_raw": classification}
        log_action({"type": "classify_gemini", "from": sender, "subject": payload.subject, "result": result})
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# VERIFY (schema-aware)
# -----------------------
@app.post("/verify")
async def verify_transaction(payload: VerifyIn):
    try:
        # 1) Firestore first
        if db:
            try:
                q = db.collection("transactions") \
                    .where("transaction_id", "==", payload.transaction_id) \
                    .where("email", "==", payload.sender_email) \
                    .limit(1).stream()
                for d in q:
                    txn = d.to_dict()
                    result = {"match": True, "transaction": txn}
                    log_action({"type": "verify", "transaction_id": payload.transaction_id, "sender": payload.sender_email, "result": result})
                    return result
            except Exception as e:
                logging.warning(f"Firestore verify error: {e}")

        # 2) txn_db module
        if txn_db and hasattr(txn_db, "lookup_transaction"):
            try:
                txn = txn_db.lookup_transaction(payload.transaction_id, payload.sender_email)
                if txn:
                    result = {"match": True, "transaction": txn}
                    log_action({"type": "verify", "transaction_id": payload.transaction_id, "sender": payload.sender_email, "result": result})
                    return result
            except Exception as e:
                logging.warning(f"txn_db lookup error: {e}")

        # 3) SQLite fallback - build SQL dynamically using only existing columns
        conn = sqlite3.connect(str(DB_PATH))
        cols = sqlite_table_columns(conn, "transactions")
        cur = conn.cursor()

        # Preferred columns to return (if they exist)
        preferred = ["transaction_id", "email", "merchant", "amount", "currency", "status", "date", "timestamp"]
        select_cols = [c for c in preferred if c in cols]

        txn_obj = None

        # Build WHERE clause depending on whether an email-like column exists
        email_column = None
        for candidate in ("email", "customer_email"):
            if candidate in cols:
                email_column = candidate
                break

        if select_cols:
            sel = ", ".join(select_cols)
            if email_column:
                sql = f"SELECT {sel} FROM transactions WHERE transaction_id=? AND (LOWER({email_column})=LOWER(?) OR {email_column}=? ) LIMIT 1"
                params = (payload.transaction_id, payload.sender_email, payload.sender_email)
            else:
                # If no email column, match by transaction_id only
                sql = f"SELECT {sel} FROM transactions WHERE transaction_id=? LIMIT 1"
                params = (payload.transaction_id,)

            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                if row:
                    txn_obj = {}
                    for idx, col in enumerate(select_cols):
                        txn_obj[col] = row[idx]
            except Exception as e:
                logging.warning(f"SQLite verify execute failed: {e}")
        else:
            # No known columns -> attempt generic row fetch by txn id
            try:
                cur.execute("SELECT * FROM transactions WHERE transaction_id=? LIMIT 1", (payload.transaction_id,))
                row = cur.fetchone()
                if row:
                    info = conn.execute("PRAGMA table_info(transactions)").fetchall()
                    colnames = [r[1] for r in info]
                    txn_obj = {colnames[i]: row[i] for i in range(min(len(colnames), len(row)))}
            except Exception as e:
                logging.warning(f"SQLite generic verify failed: {e}")

        conn.close()

        ok = txn_obj is not None
        result = {"match": ok, "transaction": txn_obj}
        log_action({"type": "verify", "transaction_id": payload.transaction_id, "sender": payload.sender_email, "result": result})
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# REPLY
# -----------------------
@app.post("/reply")
async def generate_reply(payload: ReplyIn):
    try:
        body = payload.body or ""
        sender = payload.from_email
        subject = payload.subject or ""

        # TEMPLATE MATCH FIRST
        if gmail_auth and hasattr(gmail_auth, "match_template"):
            try:
                tmpl, action, txn = gmail_auth.match_template(body, sender)
                if tmpl and payload.use_templates:
                    # Try to send template reply if Gmail service present
                    gmail_service = get_gmail_service()
                    sent = False
                    thread_id = None
                    try:
                        if gmail_service and hasattr(gmail_auth, "send_email"):
                            ok, thread_id = gmail_auth.send_email(
                                gmail_service,
                                receiver_email=sender,
                                original_subject=subject,
                                reply_body_text=tmpl,
                                original_sender_email_for_log=sender,
                                action_type="template",
                                gmail_thread_id_to_reply_in=None,
                                incoming_message_id_to_reply_to=None,
                                incoming_references_header=None
                            )
                            sent = bool(ok)
                    except Exception as e:
                        logging.warning("send_email for template failed: %s", e)

                    log_action({
                        "type": "reply_generated",
                        "source": "template",
                        "from": sender,
                        "subject": subject,
                        "reply_preview": tmpl[:400],
                        "sent": sent
                    })
                    return {"ok": True, "reply": tmpl, "source": "template", "sent": sent}
            except Exception:
                pass

        # --------- Detect TXN ID in text ---------
        txn_match = None
        m = re.search(r"\b(TXN\d+)\b", body, flags=re.IGNORECASE)
        if m:
            txn_match = m.group(1).upper()

        verified_txn = None

        if txn_match:
            # Firestore lookup
            if db:
                try:
                    q = db.collection("transactions") \
                        .where("transaction_id", "==", txn_match) \
                        .where("email", "==", sender) \
                        .limit(1).stream()
                    for d in q:
                        verified_txn = d.to_dict()
                        break
                except Exception:
                    pass

            # txn_db fallback
            if not verified_txn and txn_db and hasattr(txn_db, "lookup_transaction"):
                try:
                    t = txn_db.lookup_transaction(txn_match, sender)
                    if t:
                        verified_txn = t
                except Exception:
                    pass

            # SQLite final fallback (schema-aware)
            if not verified_txn:
                try:
                    conn = sqlite3.connect(str(DB_PATH))
                    cols = sqlite_table_columns(conn, "transactions")
                    cur = conn.cursor()
                    # prefer matching email if present
                    email_column = None
                    for candidate in ("email", "customer_email"):
                        if candidate in cols:
                            email_column = candidate
                            break

                    if email_column:
                        sql = f"""
                            SELECT transaction_id, {email_column}, merchant, amount, currency, status, date, timestamp
                            FROM transactions WHERE transaction_id=? AND (LOWER({email_column})=LOWER(?) OR {email_column}=?)
                        """
                        cur.execute(sql, (txn_match, sender, sender))
                        row = cur.fetchone()
                        if row:
                            # map to canonical keys where present
                            verified_txn = {
                                "transaction_id": row[0],
                                "email": row[1],
                                "merchant": row[2] if len(row) > 2 else None,
                                "amount": row[3] if len(row) > 3 else None,
                                "currency": row[4] if len(row) > 4 else None,
                                "status": row[5] if len(row) > 5 else None,
                                "date": row[6] if len(row) > 6 else None
                            }
                    else:
                        # fallback: find by transaction_id alone
                        cur.execute("SELECT * FROM transactions WHERE transaction_id=? LIMIT 1", (txn_match,))
                        row = cur.fetchone()
                        if row:
                            info = conn.execute("PRAGMA table_info(transactions)").fetchall()
                            colnames = [r[1] for r in info]
                            verified_txn = {colnames[i]: row[i] for i in range(min(len(colnames), len(row)))}
                    conn.close()
                except Exception:
                    pass

        # --------- Build Prompt ---------
        if verified_txn:
            extra_ctx = f"""
Verified transaction:
- ID: {verified_txn.get("transaction_id")}
- Merchant: {verified_txn.get("merchant")}
- Amount: {verified_txn.get("amount")} {verified_txn.get("currency")}
- Date: {verified_txn.get("date", verified_txn.get("timestamp", "unknown"))}

Do NOT invent any additional data.
"""
        else:
            extra_ctx = """
No verified transaction found for this customer.
Ask politely for:
- TXN ID
- Screenshot of charge
- Date & amount
"""

        prompt = f"""
You are Nova AIS, the compliance-safe assistant for a payment service provider.

Customer message:
{body}

{extra_ctx}

Rules:
- Be concise, polite, professional.
- Never invent transaction data.
- If verified_txn exists, reference ONLY verified fields.
- If none, request details.
- Avoid negative or accusatory tone.
"""

        candidate = gemini_generate(prompt)

        # ---------------- SAFETY VALIDATION ----------------
        passed = True
        reason = "no-validator"

        if gmail_auth and hasattr(gmail_auth, "validate_llm_reply"):
            try:
                passed, reason = gmail_auth.validate_llm_reply(candidate)
            except Exception:
                passed = True
                reason = "validator-error"

        # If fail: rewrite, forward, or bypass
        if not passed:
            log_action({"type": "reply_validation_failed", "reason": reason, "reply_preview": candidate[:400]})

            # If demo bypass enabled, accept regardless
            if os.environ.get("FORCE_ACCEPT_NEGATIVE", "").lower() in ("1", "true", "yes"):
                passed = True

            # If failure indicates negative sentiment or a human request, escalate to human
            escalate_keywords = ["human", "representative", "talk to", "real person", "agent", "support"]
            contains_escalation = any(k in body.lower() for k in escalate_keywords)

            if ("sentiment" in reason.lower() or "polarity" in reason.lower() or contains_escalation):
                # try forwarding to human if function available
                try:
                    gmail_service = get_gmail_service()
                    if gmail_service and gmail_auth and hasattr(gmail_auth, "forward_email_to_human"):
                        gmail_auth.forward_email_to_human(gmail_service, subject, body, sender, reason_for_forward=reason)
                        log_action({"type": "forward_due_to_validation", "from": sender, "subject": subject, "reason": reason})
                        handoff_text = "Thank you — your request has been forwarded to our human support team. A specialist will respond shortly."
                        # Also send an informational reply to the customer (non-blocking)
                        try:
                            if gmail_service and hasattr(gmail_auth, "send_email"):
                                gmail_auth.send_email(
                                    gmail_service,
                                    receiver_email=sender,
                                    original_subject=subject,
                                    reply_body_text=handoff_text,
                                    original_sender_email_for_log=sender,
                                    action_type="handoff_notification",
                                    gmail_thread_id_to_reply_in=None,
                                    incoming_message_id_to_reply_to=None,
                                    incoming_references_header=None
                                )
                        except Exception:
                            pass
                        return {"ok": True, "reply": handoff_text, "source": "forwarded_to_human"}
                except Exception as e:
                    logging.warning("Forward to human failed: %s", e)

            # If we didn't forward, attempt neutral rewrite then fallback canned reply
            if "sentiment" in reason.lower() or "polarity" in reason.lower():
                retry_prompt = f"""
Rewrite this reply to be neutral, calm, polite, and compliance-safe. DO NOT add facts.

Original:
{candidate}
"""
                candidate2 = gemini_generate(retry_prompt)
                # re-validate
                passed2 = True
                if gmail_auth and hasattr(gmail_auth, "validate_llm_reply"):
                    try:
                        passed2, _ = gmail_auth.validate_llm_reply(candidate2)
                    except Exception:
                        passed2 = True
                if passed2:
                    candidate = candidate2
                    passed = True
                else:
                    candidate = (
                        "Thank you for contacting us. "
                        "Please provide the transaction ID, date, amount, and a screenshot of the charge "
                        "so we can investigate promptly."
                    )
                    passed = True
            else:
                candidate = (
                    "Thank you for your message. "
                    "Please provide the transaction ID, date, amount, and a screenshot of the charge "
                    "so we can review this for you."
                )
                passed = True

        # ---------- Send reply (if passed) ----------
        gmail_service = get_gmail_service()
        sent = False
        thread_id = None
        if passed and gmail_service and gmail_auth and hasattr(gmail_auth, "send_email"):
            try:
                ok, thread_id = gmail_auth.send_email(
                    gmail_service,
                    receiver_email=sender,
                    original_subject=subject,
                    reply_body_text=candidate,
                    original_sender_email_for_log=sender,
                    action_type="gemini_reply",
                    gmail_thread_id_to_reply_in=None,
                    incoming_message_id_to_reply_to=None,
                    incoming_references_header=None
                )
                sent = bool(ok)
            except Exception as e:
                logging.warning("send_email threw: %s", e)
                sent = False

        log_data = {
            "type": "reply_generated",
            "source": "gemini",
            "from": sender,
            "subject": subject,
            "reply_preview": candidate[:400],
            "sent": sent
        }
        if verified_txn:
            log_data["verified_txn"] = verified_txn.get("transaction_id")

        log_action(log_data)

        return {"ok": True, "reply": candidate, "source": "gemini", "verified_txn": verified_txn, "sent": sent, "thread_id": thread_id}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# LOGS
# -----------------------
@app.get("/logs")
async def list_recent_logs(limit: int = 20):
    try:
        if db:
            items = []
            docs = db.collection("nova_ais_logs") \
                     .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                     .limit(limit).stream()
            for d in docs:
                items.append(d.to_dict())
            return {"count": len(items), "items": items}

        # Local fallback
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f.readlines() if x.strip()]
            return {"count": len(lines[-limit:]), "items": list(reversed(lines[-limit:]))}
        except FileNotFoundError:
            return {"count": 0, "items": []}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
