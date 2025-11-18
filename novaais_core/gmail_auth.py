import re
import imaplib
import smtplib
import email
import json
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart # NEW: Import MIMEMultipart
from email.mime.text import MIMEText # NEW: Import MIMEText
import email.utils
import time
import requests
import string
import re
from langdetect import detect, LangDetectException
from transaction_db_setup import lookup_transaction
import traceback # NEW: Import traceback for detailed error logging
import os
from pathlib import Path

# NEW: Imports for Gmail API Authentication
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import base64 # NEW: Import base64 for email sending
from textblob import TextBlob
from nova_ai_config import (
    BOT_REPLY_NEGATIVE_SENTIMENT_THRESHOLD, 
    UNDESIRABLE_KEYWORDS_IN_REPLY, 
    EXPECTED_SIGNATURE_PART,
    MIN_REPLY_WORD_COUNT,  # New
    MAX_REPLY_WORD_COUNT,  # New
    MAX_ALL_CAPS_WORD_LENGTH # New
)
# ========== CONFIGURATION ==========
EMAIL_ADDRESS = "tstngallen@gmail.com"
EMAIL_PASSWORD = "ckhriyljyolxfgcc" # Reminder: Keep this secure!
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
CHECK_INTERVAL = 10
FORWARD_TO_EMAIL = "tstng2allen@gmail.com"
ACTION_REPLY = "REPLY"
ACTION_FORWARD = "FORWARD"
ACTION_LLM_FALLBACK = "LLM_FALLBACK"
ACTION_SECURITY_REPLY = "SECURITY_REPLY"
OPENROUTER_API_KEY = "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" # Reminder: Keep this secure!
TEMPLATE_FILE = "templates.json"
LOGO_PATH = "Novalnet-Logo.png"
BOT_EMAIL = EMAIL_ADDRESS
LOG_FILE_PATH = "bot_sent_emails.log" # NEW: Path to log file
AI_LEARNING_FEEDBACK_LOG = "ai_learning_feedback.log"
CLEANED_FEEDBACK_FILE = "novalnet_ai_feedback_cleaned.jsonl"
CASE_KNOWLEDGE_FILE_PATH = "novalnet_case_knowledge.jsonl"  # <--- ADD THIS
CLEANED_EXAMPLES = []
LOADED_CASE_KNOWLEDGE = []  # <--- ADD THIS
CONVERSATION_HISTORY = {}
MAX_HISTORY_MESSAGES = 6 
BOT_REPLY_TO_MASTER_THREAD_MAP = {}
# ALLOWED_ACRONYMS should also be loaded or defined here from your config
ALLOWED_ACRONYMS = {"SEPA", "EUR", "BGB", "AG", "TID", "DSGVO", "SWM", "RLSK", "CMS", "CRM", "FAQ"} 

# --- NEW: SCOPES for Gmail API ---
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']
# ===================================

TEMPLATE_FILE = Path(__file__).parent / "templates.json"


# ========== LOAD TEMPLATES ==========
try:
    if TEMPLATE_FILE.exists():
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            TEMPLATES = json.load(f)
            print(f"✅ Loaded templates.json from: {TEMPLATE_FILE}")
    else:
        raise FileNotFoundError(f"Template file not found at: {TEMPLATE_FILE}")
except Exception as e:
    print(f"❌ Error loading templates.json: {e}")
    TEMPLATES = {}
# ====================================

def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in ['en', 'de'] else 'en'
    except LangDetectException:
        return 'en'

def normalize_text(text):
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return ' '.join(text.split())


def get_email_sentiment(text):
    """
    Analyzes the sentiment of a given text using TextBlob.
    Returns a dictionary with polarity and subjectivity.
    Returns default scores if text is invalid or analysis fails.
    """
    if not text or not isinstance(text, str) or not text.strip(): # Check for empty or invalid text
        # Return neutral scores for invalid input to avoid errors downstream
        return {"polarity": 0.0, "subjectivity": 0.0, "error": "Input text was empty or invalid"}
    try:
        blob = TextBlob(text)
        return {
            "polarity": blob.sentiment.polarity,
            "subjectivity": blob.sentiment.subjectivity
        }
    except Exception as e:
        print(f"⚠️ Error during sentiment analysis: {e}")
        # Return neutral scores in case of an unexpected error during analysis
        return {"polarity": 0.0, "subjectivity": 0.0, "error": str(e)}


def validate_llm_reply(reply_text):
    """
    Validates a generated LLM reply for tone, keywords, length, and other issues.
    Returns a tuple: (is_valid, reason_if_invalid)
    """
    if not reply_text or not isinstance(reply_text, str) or not reply_text.strip():
        return False, "LLM reply was empty or not a string."
        
    words = reply_text.split()
    word_count = len(words)

    # Check 1: Sentiment of the bot's reply
    reply_sentiment = get_email_sentiment(reply_text) # Assumes get_email_sentiment is defined
    if reply_sentiment.get('polarity', 0.0) < BOT_REPLY_NEGATIVE_SENTIMENT_THRESHOLD:
        reason = f"Sentiment too negative (Polarity: {reply_sentiment.get('polarity', 0.0):.2f})."
        print(f"⚠️ LLM reply validation failed: {reason}")
        return False, reason

    # Check 2: Keyword Block-list
    for keyword in UNDESIRABLE_KEYWORDS_IN_REPLY:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, reply_text.lower()):
            reason = f"Contains undesirable keyword ('{keyword}')."
            print(f"⚠️ LLM reply validation failed: {reason}")
            return False, reason
            
    # Check 3: Basic Signature Check
    if EXPECTED_SIGNATURE_PART.lower() not in reply_text.lower():
        reason = f"Missing expected signature part ('{EXPECTED_SIGNATURE_PART}')."
        print(f"⚠️ LLM reply validation failed: {reason}")
        return False, reason

    # Check 4: Minimum Reply Length
    if word_count < MIN_REPLY_WORD_COUNT:
        reason = f"Reply too short (Words: {word_count}, Minimum: {MIN_REPLY_WORD_COUNT})."
        print(f"⚠️ LLM reply validation failed: {reason}")
        return False, reason

    # Check 5: Maximum Reply Length
    if word_count > MAX_REPLY_WORD_COUNT:
        reason = f"Reply too long (Words: {word_count}, Maximum: {MAX_REPLY_WORD_COUNT})."
        print(f"⚠️ LLM reply validation failed: {reason}")
        return False, reason

    # Check 6: Excessive ALL CAPS
    for word in words:
        if not word: # Skip empty strings if any result from split
            continue
            
        is_word_all_caps = word.isupper() # Check original word for isupper()
        
        if is_word_all_caps and len(word) > MAX_ALL_CAPS_WORD_LENGTH:
            # Clean the word: remove leading/trailing non-alphanumeric characters
            # e.g., "(BRL)," becomes "BRL", "TXN001." becomes "TXN001"
            cleaned_word_for_check = re.sub(r'^\W+|\W+$', '', word)

            if not cleaned_word_for_check: # If cleaning makes it empty (e.g., word was just punctuation like "---")
                 continue

            # Check 6a: Is it a known TID-like pattern? (e.g., TXN123, TID12345)
            # This pattern checks if the cleaned word starts with TXN/TID/TRX and is followed by digits and optionally A-Z, 0-9, _
            if re.fullmatch(r'(?:TXN|TID|TRX)\d+[A-Z0-9_]*', cleaned_word_for_check, re.IGNORECASE):
                print(f"    DEBUG_VALIDATE: Word '{word}' (cleaned: '{cleaned_word_for_check}') matched TID pattern, allowed.")
                continue # Allowed, skip to next word

            # Check 6b: Is it a common 3-letter uppercase code (often currencies)?
            if re.fullmatch(r'[A-Z]{3}', cleaned_word_for_check):
                print(f"    DEBUG_VALIDATE: Word '{word}' (cleaned: '{cleaned_word_for_check}') matched 3-letter ALL CAPS pattern, allowed.")
                continue # Allowed, skip to next word
            
            # Check 6c: Is it in the general list of allowed acronyms?
            if cleaned_word_for_check not in ALLOWED_ACRONYMS: 
                reason = f"Excessive use of ALL CAPS (word: '{word}' -> checked as '{cleaned_word_for_check}')."
                print(f"⚠️ LLM reply validation failed: {reason}")
                return False, reason
            else: # If it's in ALLOWED_ACRONYMS
                print(f"    DEBUG_VALIDATE: Word '{word}' (cleaned: '{cleaned_word_for_check}') found in ALLOWED_ACRONYMS, allowed.")
                continue

    # Check 7: Unresolved Placeholders
    if re.search(r"\[[A-Z0-9_]{3,}\]", reply_text) or \
       re.search(r"<<[A-Z0-9_]{3,}>>", reply_text) or \
       re.search(r"\{\{[A-Z0-9_]{3,}\}\}", reply_text):
        reason = "Reply appears to contain an unresolved placeholder."
        print(f"⚠️ LLM reply validation failed: {reason}")
        return False, reason

    return True, "LLM reply passed validation."


def load_templates(file_path):
    """Loads templates from a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            templates_data = json.load(f)
            print(f"✅ Loaded templates from '{file_path}'.")
            return templates_data
    except FileNotFoundError:
        print(f"❌ Error: Template file not found at '{file_path}'.")
        return {}
    except Exception as e:
        print(f"❌ An unexpected error occurred while loading {file_path}: {e}")
        return {}

def load_cleaned_feedback_examples(file_path):
    """Loads cleaned email-reply pairs from a JSON Lines file."""
    examples = []
    if not os.path.exists(file_path):
        print(f"Warning: Cleaned feedback file not found at '{file_path}'.")
        return examples
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
        print(f"✅ Loaded {len(examples)} cleaned feedback examples from '{file_path}'.")
    except Exception as e:
        print(f"❌ Error loading cleaned feedback examples: {e}")
    return examples

def load_case_knowledge(file_path):
    """Loads structured case knowledge entries from a JSON Lines file."""
    cases = []
    if not os.path.exists(file_path):
        print(f"⚠️ Case knowledge file not found at '{file_path}'.")
        return cases
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    cases.append(json.loads(line))
        print(f"✅ Loaded {len(cases)} case knowledge entries from '{file_path}'.")
    except Exception as e:
        print(f"❌ Error loading case knowledge: {e}")
    return cases


def load_cleaned_feedback_examples(file_path):
    """
    Loads cleaned email-reply pairs from a JSON Lines file.
    """
    examples = []
    if not os.path.exists(file_path):
        print(f"Warning: Cleaned feedback file not found at '{file_path}'. AI will not use few-shot examples.")
        return examples
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        # We only care about the cleaned body and reply for examples
                        examples.append({
                            "original_email_body_cleaned": entry.get("original_email_body_cleaned", ""),
                            "human_ideal_reply_cleaned": entry.get("human_ideal_reply_cleaned", "")
                        })
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON in cleaned feedback file: {e} in line: '{line}'")
                        continue
        print(f"✅ Loaded {len(examples)} cleaned feedback examples from '{file_path}'.")
    except Exception as e:
        print(f"❌ Error loading cleaned feedback examples: {e}")
    return examples

def load_case_knowledge(file_path):
    """
    Loads structured case knowledge entries from a JSON Lines file.
    Each line should be a JSON object representing a case.
    """
    cases = []
    if not os.path.exists(file_path): # Make sure 'import os' is at the top of your script
        print(f"⚠️ Case knowledge file not found at '{file_path}'. No case knowledge will be loaded.")
        return cases
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        # Basic check if essential fields are present (you can expand this)
                        if "case_title" in entry and "todo_de" in entry:
                            cases.append(entry)
                        else:
                            print(f"   Skipping invalid case entry (e.g., missing 'case_title') on line {line_number} in '{file_path}'")
                    except json.JSONDecodeError as e:
                        print(f"   Error decoding JSON in case knowledge file on line {line_number}: {e} in line: '{line}'")
                        continue
        print(f"✅ Loaded {len(cases)} case knowledge entries from '{file_path}'.")
    except Exception as e:
        print(f"❌ Error loading case knowledge: {e}")
    return cases

# Basic stop word lists (can be expanded or moved to nova_ai_config.py if they grow large)
STOP_WORDS_EN = set([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "can", "could", "may", "might", "must", "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "to", "of", "in", "on", "at",
    "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below",
    "from", "up", "down", "out", "over", "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "just", "don", "shouldve", "now",
    "d", "ll", "m", "o", "re", "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn", "hasn", "haven",
    "isn", "ma", "mightn", "mustn", "needn", "shan", "shouldn", "wasn", "weren", "won", "wouldn",
    "thank", "thanks", "please", "hello", "dear", "regards", "best", "kind", "sincerely", "hi"
])

STOP_WORDS_DE = set([
    "der", "die", "das", "ein", "eine", "eines", "einer", "einem", "einen", "und", "oder", "aber", "sondern",
    "wenn", "dann", "als", "dass", "nicht", "ich", "du", "er", "sie", "es", "wir", "ihr", "sie", "sich", "mich",
    "dich", "uns", "euch", "mein", "dein", "sein", "ihr", "unser", "euer", "ihre", "meine", "deine", "seine",
    "meinen", "deinen", "seinen", "meinem", "deinem", "seinem", "meiner", "deiner", "seiner", "zu", "von",
    "mit", "auf", "aus", "bei", "nach", "seit", "vor", "für", "um", "durch", "ohne", "gegen", "über", "unter",
    "zwischen", "auch", "noch", "schon", "sehr", "bitte", "danke", "hallo", "herr", "frau", "geehrte", "geehrter",
    "freundlichen", "grüßen", "mfg", "gruß", "wurde", "kann", "habe", "bin", "sind", "hat", "im", "den", "dem",
    "des", "ja", "nein", "vielleicht", "hier", "dort", "man", "hatte", "ihm", "ihn", "ihnen", "ihrer", "ihres",
    "ihrem", "ihren", "da", "wo", "warum", "wie", "was", "welche", "welcher", "welches", "während", "ob", "damit",
    "also", "denn", "doch", "eben", "falls", "fast", "fort", "gar", "gern", "gemäß", "hab", "hätt", "hätte",
    "hin", "hinter", "jede", "jedem", "jeden", "jeder", "jedes", "jemand", "jemandem", "jemanden", "jene", "jenem",
    "jenen", "jener", "jenes", "jetzt", "kam", "konnte", "könnte", "machen", "mal", "manche", "manchem", "manchen",
    "mancher", "manches", "mein", "meist", "meiste", "meisten", "nachdem", "namentlich", "neben", "nirgends",
    "noch", "nun", "nur", "obgleich", "oft", "per", "plötzlich", "pro", "rund", "sa", "sagt", "sagte", "sagtst",
    "samt", "sowie", "sobald", "solche", "solchem", "solchen", "solcher", "solches", "soll", "sollte", "sonst",
    "sooft", "soviel", "soweit", "später", "statt", "tat", "teil", "tel", "total", "trotz", "tun", "überall",
    "übrigens", "umso", "viel", "viele", "vielem", "vielen", "vielleicht", "vom", "voran", "vorbei", "vorgestern",
    "vorher", "vorhin", "vorne", "währenddessen", "wann", "war", "wäre", "waren", "wart", "was", "wegen", "weil",
    "weiter", "weitere", "weiteres", "weiterhin", "welchem", "welchen", "welcher", "welches", "wem", "wen",
    "wenig", "wenige", "weniger", "wenigstens", "wer", "werde", "werden", "werdet", "weshalb", "wessen", "wie",
    "wieder", "wieso", "will", "wirklich", "wird", "wirst", "wodurch", "woher", "wohin", "wohl", "wolle", "wollen",
    "wollt", "wollte", "wollten", "worden", "während", "würde", "würden", "z.b.", "zuerst", "zugleich", "zum",
    "zunächst", "zur", "zurück", "zusammen", "zzgl", "ca", "d.h", "usw", "etc"
])

def get_significant_words(text, lang):
    """Normalizes text, splits into words, and removes stop words."""
    normalized = normalize_text(text)
    words = normalized.split()
    stop_words = STOP_WORDS_DE if lang == 'de' else STOP_WORDS_EN
    return [word for word in words if word not in stop_words and len(word) > 1]

# In gmail_auth.py

def find_relevant_cases(email_body_text, all_loaded_cases, num_results=1):
    """
    Finds relevant cases from loaded knowledge based on curated keywords, title, and explanation.
    """
    if not email_body_text or not all_loaded_cases:
        return []

    email_lang = detect_language(email_body_text)
    significant_email_words = set(get_significant_words(email_body_text, email_lang))

    if not significant_email_words:
        print("    DEBUG: No significant words found in email after stop word removal.")
        return []

    print(f"    DEBUG: Significant email words ({email_lang}): {significant_email_words}")

    relevant_cases_with_scores = []

    for case_idx, case_data in enumerate(all_loaded_cases):
        score = 0
        debug_scores = {"curated_keywords": 0, "title_keywords": 0, "explanation_keywords": 0}

        # --- Score from Curated Keywords (highest weight) ---
        case_keywords_de_phrases = case_data.get("match_keywords_de", [])
        case_keywords_en_phrases = case_data.get("match_keywords_en", [])
        
        relevant_case_keyword_phrases = case_keywords_de_phrases if email_lang == 'de' else case_keywords_en_phrases
        
        # Fallback: if email lang is 'en' but no 'en' keywords, try 'de' keywords, and vice-versa
        # CORRECTED LINES BELOW:
        if not relevant_case_keyword_phrases and email_lang == 'en' and case_keywords_de_phrases:
            relevant_case_keyword_phrases = case_keywords_de_phrases
        elif not relevant_case_keyword_phrases and email_lang == 'de' and case_keywords_en_phrases:
            relevant_case_keyword_phrases = case_keywords_en_phrases
        # END CORRECTED LINES
            
        all_curated_significant_words = set()
        for phrase in relevant_case_keyword_phrases:
            all_curated_significant_words.update(get_significant_words(phrase, email_lang)) 

        if case_data.get("case_title") == "Betrug": # Specific debug for "Betrug"
            print(f"      DEBUG for 'Betrug' case (Index: {case_idx}):")
            print(f"         Original match_keywords_en (from JSON): {case_keywords_en_phrases}")
            print(f"         Selected relevant_case_keyword_phrases: {relevant_case_keyword_phrases}")
            print(f"         Processed all_curated_significant_words (for matching lang): {all_curated_significant_words}")
            # print(f"         Comparing with significant_email_words: {significant_email_words}") # Already printed above

        common_curated_keywords = significant_email_words.intersection(all_curated_significant_words)
        
        if case_data.get("case_title") == "Betrug": # More debug for Betrug
            print(f"         Common curated keywords for 'Betrug': {common_curated_keywords}")

        if common_curated_keywords:
            score += len(common_curated_keywords) * 10
            debug_scores["curated_keywords"] = len(common_curated_keywords) * 10

        # --- Score from Case Title (medium weight) ---
        case_title_text = case_data.get("case_title", "")
        if case_title_text: 
            case_title_significant_words = set(get_significant_words(case_title_text, email_lang)) 
            common_title_words = significant_email_words.intersection(case_title_significant_words)
            if common_title_words:
                score += len(common_title_words) * 3 
                debug_scores["title_keywords"] = len(common_title_words) * 3

        # --- Score from Detailed Explanation (lower weight) ---
        explanation_text_de = case_data.get("detailed_explanation_de", "")
        if explanation_text_de: 
            explanation_significant_words = set(get_significant_words(explanation_text_de, "de")) # Assume explanation is German
            common_expl_words = significant_email_words.intersection(explanation_significant_words)
            score += len(common_expl_words) * 1
            debug_scores["explanation_keywords"] = len(common_expl_words) * 1
            
        if score > 0:
            relevant_cases_with_scores.append({
                "case": case_data, 
                "score": score,
                "debug_scores": debug_scores,
                "original_index": case_idx
            })

    sorted_cases = sorted(relevant_cases_with_scores, key=lambda x: x["score"], reverse=True)
    
    print("    All cases with score > 0 (before MIN_RELEVANCE_SCORE filter):")
    if not relevant_cases_with_scores: 
        print("      No cases received any positive score.")
    else:
        printed_count = 0
        for i, item in enumerate(sorted_cases):
            if item['score'] > 0:
                print(f"      {i+1}. Title: '{item['case'].get('case_title')}' (Index: {item['original_index']}), Score: {item['score']}")
                print(f"         Debug: Curated={item['debug_scores']['curated_keywords']}, Title={item['debug_scores']['title_keywords']}, Explanation={item['debug_scores']['explanation_keywords']}")
                printed_count +=1
        if printed_count == 0: 
            print("      No cases received any score > 0 to display (e.g. all scores were 0).")
            
    MIN_RELEVANCE_SCORE = 5 
    final_relevant_cases = [item for item in sorted_cases if item['score'] >= MIN_RELEVANCE_SCORE]

    if final_relevant_cases:
        print(f"    Top relevant cases PASSED MIN_RELEVANCE_SCORE of {MIN_RELEVANCE_SCORE} (up to {num_results} shown below):")
        for i, item in enumerate(final_relevant_cases[:num_results]): 
             print(f"      {i+1}. Title: '{item['case'].get('case_title')}' (Index: {item['original_index']}), Score: {item['score']}")
             print(f"         Final Debug Scores: Curated={item['debug_scores']['curated_keywords']}, Title={item['debug_scores']['title_keywords']}, Explanation={item['debug_scores']['explanation_keywords']}")
            
    return [item["case"] for item in final_relevant_cases[:num_results]]

def is_trigger_matched(email_text, trigger):
    normalized_email = normalize_text(email_text)
    normalized_trigger = normalize_text(trigger)
    return normalized_trigger in normalized_email

import re # Make sure 'import re' is at the top of your gmail_auth.py file

def extract_transaction_id(body):
    """
    Extracts a Novalnet Transaction ID (TID) from the email body.
    Prioritizes TIDs with explicit prefixes and specific lengths.
    Returns the full matched ID string (e.g., "TXN001" or a 17-digit number).
    """
    if not body or not isinstance(body, str): # Basic check for valid input
        return None

    # Pattern 1: Look for common explicit prefixes like "TID", "Transaction ID", 
    # "Transaktions-ID", "TXN", or "TRX".
    # These can be followed by an optional colon, hyphen, or space(s).
    # It then looks for a sequence of 3 to 19 digits.
    # The outer parentheses create a capturing group for the entire match (e.g., "TXN001").
    match_prefix = re.search(
        r'\b((?:TID|Transaction ID|Transaktions-ID|TXN|TRX)\s*[:\-]?\s*\d{3,19})\b', 
        body,
        re.IGNORECASE  # Makes the prefix search case-insensitive
    )
    if match_prefix:
        extracted_id = match_prefix.group(1) # group(1) now captures the whole "TXN001" or "TID 123..."
        print(f"    DEBUG: TID found with prefix: {extracted_id}")
        return extracted_id

    # Pattern 2: If no prefixed ID is found, look for a standalone 17-digit number.
    # This is based on observing that Novalnet TIDs are frequently 17 digits long.
    match_standalone_17digit = re.search(r'\b(\d{17})\b', body) # \b ensures it's a whole number
    if match_standalone_17digit:
        tid_candidate = match_standalone_17digit.group(1)
        
        # Simple heuristic to avoid matching numbers in contexts like copyright lines or other typical non-TID number locations
        start_index = match_standalone_17digit.start()
        chars_before_window = body[max(0, start_index - 20) : start_index].lower() 
        context_skip_terms = ["©", "copyright", "jahr", "gmbh", "inc.", "ltd.", "version", "hgb", "ust-idnr", "hrb", "tel:", "fax:", "vat id", "tax id", "reg no"] 
        
        if any(term in chars_before_window for term in context_skip_terms):
            print(f"    DEBUG: Standalone 17-digit number '{tid_candidate}' found, but context ('{chars_before_window[-15:]}...') suggests it might not be a TID. Skipping.")
            return None # Skip if context is suspicious
        
        print(f"    DEBUG: Standalone 17-digit TID found: {tid_candidate} (context before: '{chars_before_window[-15:]}')")
        return tid_candidate

    print(f"    DEBUG: No clear Transaction ID found in body with refined patterns.")
    return None

def is_human_agent_reply(msg):
    """
    Checks if an email is likely a reply from the human agent (FORWARD_TO_EMAIL)
    that was CC'd to the bot's main email address.
    """
    sender_email = email.utils.parseaddr(msg.get('From', ''))[1].lower()
    
    # Check if the sender is the human agent's email
    # Note: FORWARD_TO_EMAIL is the human agent's inbox, which is where they reply FROM.
    if sender_email != FORWARD_TO_EMAIL.lower():
        return False

    # Check if the bot's email is in To or Cc (indicating it was CC'd/BCC'd)
    # Note: BCC recipients are not visible in headers, so we rely on CC or To.
    recipients = msg.get('To', '') + ' ' + msg.get('Cc', '')
    if EMAIL_ADDRESS.lower() not in recipients.lower():
        return False
    
    # Check if the subject indicates a reply to a forwarded email from the bot
    # The bot's forwarded emails have subjects starting with "[ACTION REQUIRED - AI FORWARD]"
    subject = str(make_header(decode_header(msg.get('Subject', '')))).lower()
    if not subject.startswith('re: [action required - ai forward]'):
        return False

    print(f"✅ Identified human agent reply from {sender_email} for subject: {subject}")
    return True

def extract_human_reply_and_original_body(msg):
    """
    Extracts the human agent's reply and the original customer's email body
    from a multi-part email message, typically a reply to a forwarded email.
    """
    human_reply_text = ""
    original_customer_body_text = "" # Renamed for clarity
    full_plain_text = ""
    
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            charset = part.get_content_charset() or 'utf-8'
            try:
                full_plain_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                break 
            except Exception as e:
                print(f"Error decoding email part: {e}")
                continue

    if not full_plain_text:
        print("⚠️ No plain text content found in human agent's reply email.")
        return "", "Original context not fully extracted." # Return a placeholder

    original_message_marker = "--- Original Message ---"
    marker_pos = full_plain_text.find(original_message_marker)

    if marker_pos != -1:
        human_reply_text = full_plain_text[:marker_pos].strip()
        content_after_marker = full_plain_text[marker_pos + len(original_message_marker):].strip()

        # More robustly find the actual customer message after "Body:"
        # This pattern looks for "Body:" and captures everything after it.
        # It assumes "Body:" will be on its own line or after "Sender: ... \n"
        body_match = re.search(r"(?:Sender:.*?\n)?\s*Body:\s*(.*)", content_after_marker, re.IGNORECASE | re.DOTALL)
        if body_match:
            original_customer_body_text = body_match.group(1).strip()
        else:
            # If "Body:" not found clearly after marker, maybe the rest of content_after_marker is it?
            # This is a fallback and might include "Sender:" line if present.
            print(f"⚠️ Marker '--- Original Message ---' found, but 'Body:' line not clearly parsed after it. Using content after marker as potential original body.")
            original_customer_body_text = content_after_marker 
            # It's better to return this potentially "dirty" version than "Original context not fully extracted."
            # if we have *something* after the marker.
            # The clean_feedback_data.py script can then try its best.
            if not original_customer_body_text.strip(): # If it's just whitespace after marker
                 original_customer_body_text = "Original context not fully extracted after marker."


        # --- Clean up the Human Reply Part ---
        # (Your existing bot_header_patterns and reply_headers_patterns to clean human_reply_text go here)
        # For brevity, I'm not repeating them, but ensure they are effective.
        # Example of one:
        bot_header_patterns = [
            r"On\s+[A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s+(?:AM|PM)?\s+<.*?>\s+wrote:",
            r"On\s+.*?\s+wrote:",
            # Add other patterns to remove from the TOP of human_reply_text
        ]
        for pattern in bot_header_patterns:
            human_reply_text = re.sub(re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL), "", human_reply_text).strip()
        human_reply_text = re.sub(r'\n\s*\n', '\n\n', human_reply_text).strip()


    else: # Marker not found
        print("⚠️ '--- Original Message ---' marker not found. Assuming entire email is human reply.")
        human_reply_text = full_plain_text.strip()
        original_customer_body_text = "Original context not fully extracted (no marker)."


    # Final check on original_customer_body_text
    if not original_customer_body_text.strip() or "Original context not fully extracted" in original_customer_body_text :
        if "Original context not fully extracted" not in original_customer_body_text : # Avoid redundant message
             print(f"⚠️ Final original_customer_body_text is empty or problematic. Full text was: '{full_plain_text[:300]}...'")
        # Keep the placeholder if extraction failed
        if not original_customer_body_text.strip():
            original_customer_body_text = "Original context not fully extracted (final check)."


    # Apply generic cleaning to both parts before returning
    # This uses functions that should be defined in your clean_feedback_data.py
    # or you can define them within gmail_auth.py if preferred for this specific function.
    # For now, I'll assume they are available or you'll integrate them.
    # human_reply_text = _normalize_whitespace(clean_common_artifacts(human_reply_text))
    # original_customer_body_text = _normalize_whitespace(clean_common_artifacts(original_customer_body_text))
    # Given clean_feedback_data.py does extensive cleaning, let's ensure this function provides
    # the best possible *raw separation* first. The downstream script will do the fine cleaning.

    return human_reply_text, original_customer_body_text


def match_template(email_body, sender_email):
    body_lower = email_body.lower()
    lang = detect_language(email_body)
    print(f"Detected language: {lang}")
    txn_id = extract_transaction_id(email_body)
    txn_data = lookup_transaction(txn_id, sender_email) if txn_id else None

    # --- 1. Check for "Forward to Human" trigger ---
    for template_name, template_data in TEMPLATES.items():
        if (("Forward to Human" in template_name and template_data.get("language") == "en") or
            ("Anfrage an Menschen weiterleiten" in template_name and template_data.get("language") == "de")):
            for trigger in template_data.get("triggers", []):
                if is_trigger_matched(email_body, trigger):
                    print(f"🚨 Matched 'Forward to Human' trigger: '{trigger}'")
                    return None, ACTION_FORWARD, None # Return three values

    # --- 2. Security check for TID mismatch ---
    if txn_id and not txn_data:
        print("❌ Transaction ID mismatch or not found for this email.")
        security_response = (
            f"Hello,\n\nFor security reasons, we can only process requests from the registered email address associated "
            f"with the transaction ID {txn_id}. Please resend your request from the original email address used during the payment.\n\n"
            "If you believe this is a mistake, feel free to contact our support team.\n\n"
            "Best regards,\nNovalnet Support"
        )
        return security_response, ACTION_SECURITY_REPLY, None # Return three values

    # --- 3. Check for specific "Transaction Details Request" template ---
    if txn_id and txn_data:
        for template_name, data in TEMPLATES.items():
            if data.get("language") == lang and "transaction details" in template_name.lower():
                for trigger in data.get("triggers", []):
                    if is_trigger_matched(email_body, trigger):
                        print(f"✅ Matched dedicated transaction details template: {template_name}")
                        response = data.get("response", "")
                        details_string = (
                            f"- ID: {txn_data['transaction_id']}\n"
                            f"- Merchant: {txn_data['merchant_name']}\n"
                            f"- Amount: {txn_data['amount']} {txn_data['currency']}\n"
                            f"- Method: {txn_data['payment_method']}"
                        )
                        response = response.replace('[TRANSACTION_DETAILS]', details_string)
                        response = re.sub(r'\[.*?\]', '', response)
                        return response.strip(), ACTION_REPLY, txn_data # Return three values

    # --- 4. Check general templates ---
    for template_name, data in TEMPLATES.items():
        if (("Forward to Human" in template_name) or ("Anfrage an Menschen weiterleiten" in template_name)):
            continue
        if data.get("language") != lang:
            continue
        for trigger in data.get("triggers", []):
            if is_trigger_matched(email_body, trigger):
                print(f"✅ Matched general template: {template_name}")
                response = data.get("response", "")
                return response.strip(), ACTION_REPLY, txn_data # Return three values

    print("⚠️ No template matched in language:", lang)
    return None, ACTION_LLM_FALLBACK, txn_data # Return three values

def get_thread_id_from_headers(message_id_header, references_header):
    """
    Determines a consistent thread identifier for an email.
    Prefers the first Message-ID in the 'References' header if available.
    Otherwise, uses the email's own 'Message-ID' (cleaned) as the thread_id.
    """
    thread_id = None
    if references_header:
        # References header can be a list of Message-IDs, typically space-separated.
        # Each Message-ID is often enclosed in <>. We want the first one.
        # Example: "<id1@example.com> <id2@example.com>"
        # Extract the content of the first Message-ID found.
        match = re.match(r'\s*<([^>]+)>', references_header) # Find first item in <...>
        if match:
            thread_id = match.group(1)
        else:
            # If no angle brackets around the first ID, take the first space-separated token
            # This is a fallback and might need refinement if References format varies a lot
            parts = references_header.split()
            if parts:
                thread_id = parts[0].strip().lstrip('<').rstrip('>') # Clean it just in case
    
    if not thread_id and message_id_header:
        # If no References header, or couldn't parse it, this email might be starting a new thread.
        # Use its own Message-ID (cleaned of <>) as the thread identifier.
        thread_id = message_id_header.strip().lstrip('<').rstrip('>')
        
    return thread_id

def get_latest_email():
    """
    Connects to IMAP, fetches all unseen emails, and returns their parsed data
    along with the raw message objects and extracted threading info.
    Marks emails as seen after fetching.
    """
    print("Connecting to IMAP...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        if not email_ids:
            print("No new emails.")
            mail.logout()
            return [] 

        emails_to_process = []
        for email_id in email_ids:
            result, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = str(make_header(decode_header(msg["subject"] or ""))).replace('\n', ' ').replace('\r', ' ')
            sender = msg["from"]
            _, sender_email = email.utils.parseaddr(sender)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            break
                        except:
                            continue
            else:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')

            message_id_header = msg.get("Message-ID")
            in_reply_to_header = msg.get("In-Reply-To")
            references_header = msg.get("References")
            
            thread_identifier = get_thread_id_from_headers(message_id_header, references_header)
            
            mail.store(email_id, '+FLAGS', '\\Seen')

            emails_to_process.append((sender_email, subject, body, msg, 
                                      message_id_header, in_reply_to_header, references_header, 
                                      thread_identifier)) 

        mail.logout()
        return emails_to_process
    except Exception as e:
        print(f"❌ Error fetching email: {e}")
        return []

def generate_reply_with_openrouter(email_body, retrieved_context_str=None, conversation_history=None, transaction_details=None):
    try:
        lang = detect_language(email_body)
        lang_instruction = "Reply in German." if lang == "de" else "Reply in English."

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = { "Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json" }

        system_prompt_content = (
            f"You are NOVA-AI, a professional and secure email assistant for Novalnet AG. "
            f"{lang_instruction} Keep the tone polite, helpful, and neutral. "
            "End with: 'Best regards,\\nNovalnet Support'.\n"
            "Pay close attention to any provided conversation history to understand the context of the current email and avoid asking for information already given or repeating previous statements."
        )
        
        if transaction_details:
             system_prompt_content += (
                f"\n\n## VERIFIED TRANSACTION DETAILS:\n"
                f"The following transaction details have been looked up from the database and are verified. "
                f"Use this data to answer the user's questions about this specific transaction. Provide all details clearly and directly.\n"
                f"- Transaction ID: {transaction_details['transaction_id']}\n"
                f"- Merchant: {transaction_details['merchant_name']}\n"
                f"- Amount: {transaction_details['amount']} {transaction_details['currency']}\n"
                f"- Payment Method: {transaction_details['payment_method']}\n"
                f"- Transaction Date: {transaction_details['date']}\n"
            )

        if retrieved_context_str:
            system_prompt_content += (
                f"\n\n## IMPORTANT CONTEXT FROM NOVALNET KNOWLEDGE BASE FOR THIS SPECIFIC INQUIRY:\n"
                f"{retrieved_context_str}\n\n" 
                f"### Instructions for using the provided context:\n"
                f"- If a 'Full German Standard Response Template (SWM Vorlage)' is provided...adapt this German template...\n" # Abbreviated for brevity
                f"- If no full German template is provided, or if the reply is in English, use the other details...\n"
                f"- Base your reply on the provided context as much as possible."
            )
        
        messages = [{"role": "system", "content": system_prompt_content}]

        if conversation_history: 
            print(f"    DEBUG: Including {len(conversation_history)} messages from history in LLM prompt.")
            for turn in conversation_history:
                if turn.get('role') in ['user', 'assistant'] and 'content' in turn:
                    messages.append({ "role": turn['role'], "content": turn['content'] })

        num_examples_to_use = min(5, len(CLEANED_EXAMPLES))
        for i in range(num_examples_to_use):
            example = CLEANED_EXAMPLES[i]
            if "original_email_body_cleaned" in example and "human_ideal_reply_cleaned" in example:
                messages.append({"role": "user", "content": f"Customer Email Example:\n{example['original_email_body_cleaned']}"})
                messages.append({"role": "assistant", "content": f"Ideal Human Agent Reply Example:\n{example['human_ideal_reply_cleaned']}"})

        messages.append({"role": "user", "content": f"Current Customer Email requiring response (this is the latest message in the conversation):\n{email_body}"})

        payload = { "model": "gpt-4o-mini", "messages": messages, "max_tokens": 450, "temperature": 0.5 }
        
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        
        reply = response.json()["choices"][0]["message"]["content"].strip()
        
        if EXPECTED_SIGNATURE_PART.lower() not in reply.lower():
            reply += f"\n\nBest regards,\n{EXPECTED_SIGNATURE_PART}"

        return reply
    except Exception as e:
        print(f"❌ OpenRouter API error in generate_reply_with_openrouter: {e}")
        print(traceback.format_exc())
        return None

def build_html_email(text_body):
    safe_body = text_body.replace('\n', '<br>')
    return f"""
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; background-color: #f9f9f9; padding: 30px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 10px; padding: 30px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);">
            <img src="cid:novalnetlogo" alt="Novalnet Logo" width="140" style="display: block; margin: 0 auto 25px;" />
            <div style="font-size: 15px; line-height: 1.7; color: #333333;">
                {safe_body}
            </div>
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e0e0e0;">
            <div style="font-size: 12px; color: #999999; text-align: center;">
                This is an automated message from <strong>NOVA-AI</strong>, Novalnet’s email assistant.
            </div>
        </div>
    </body>
    </html>
    """

def log_sent_email(original_sender, recipient, subject, body_text, html_body, action_type):
    """Logs details of an email sent or forwarded by the bot to a JSON Lines file."""
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "original_sender": original_sender,
        "bot_action_type": action_type,
        "recipient": recipient,
        "email_subject": subject,
        "email_body_text": body_text,
        "email_body_html": html_body # Store HTML content if available
    }
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"📊 Logged email action: {action_type} to {recipient}")
    except Exception as e:
        print(f"❌ Error logging email to file: {e}")

def log_ai_feedback(original_email_body, human_ideal_reply):
    """Logs the original email body and the human's ideal reply for AI learning."""
    feedback_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "original_email_body": original_email_body,
        "human_ideal_reply": human_ideal_reply
    }
    try:
        with open(AI_LEARNING_FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry) + "\n")
        print(f"🧠 Logged human feedback for AI learning.")
    except Exception as e:
        print(f"❌ Error logging AI feedback: {e}")

def send_email(
    gmail_service,
    receiver_email, 
    original_subject, 
    reply_body_text, 
    original_sender_email_for_log, 
    action_type, 
    # Threading information:
    gmail_thread_id_to_reply_in,     
    incoming_message_id_to_reply_to, 
    incoming_references_header
):
    actual_gmail_thread_id_from_send = None 
    try:
        print(f"📤 Preparing to send email to {receiver_email}. Intended Gmail thread: {gmail_thread_id_to_reply_in}")
        
        msg = EmailMessage()
        cleaned_subject = original_subject.replace('\n', ' ').replace('\r', ' ')
        msg["Subject"] = f"Re: {cleaned_subject}" if not cleaned_subject.lower().startswith("re:") else cleaned_subject
        msg["From"] = BOT_EMAIL 
        msg["To"] = receiver_email
        
        if incoming_message_id_to_reply_to:
            msg["In-Reply-To"] = incoming_message_id_to_reply_to
            new_references = f"{incoming_references_header} {incoming_message_id_to_reply_to}".strip() if incoming_references_header else incoming_message_id_to_reply_to
            msg["References"] = new_references

        msg.set_content(reply_body_text)
        html_body = build_html_email(reply_body_text)
        msg.add_alternative(html_body, subtype='html')

        try:
            html_part = next((part for part in msg.iter_parts() if part.get_content_subtype() == 'html'), None)
            if html_part:
                with open(LOGO_PATH, 'rb') as img_file:
                    html_part.add_related(img_file.read(), 'image', 'png', cid='novalnetlogo')
        except FileNotFoundError:
            print(f"⚠️ Logo file not found at {LOGO_PATH}.")
        except Exception as e_logo:
            print(f"⚠️ Error attaching logo: {e_logo}")

        if 'Message-ID' not in msg:
            msg['Message-ID'] = email.utils.make_msgid(domain="nova-ai.novalnet.de") 
        
        bot_reply_message_id_header_val = msg['Message-ID']
        cleaned_bot_reply_msg_id = bot_reply_message_id_header_val.strip().lstrip('<').rstrip('>') 
            
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message_to_send_payload = {'raw': raw_message}
        
        if gmail_thread_id_to_reply_in: 
            message_to_send_payload['threadId'] = gmail_thread_id_to_reply_in
            
        sent_message_details = gmail_service.users().messages().send(userId='me', body=message_to_send_payload).execute()
        
        actual_gmail_thread_id_from_send = sent_message_details.get('threadId') 
        print(f"    DEBUG: Email sent. Gmail API Thread ID: {actual_gmail_thread_id_from_send}")

        if cleaned_bot_reply_msg_id and actual_gmail_thread_id_from_send:
            BOT_REPLY_TO_MASTER_THREAD_MAP[cleaned_bot_reply_msg_id] = actual_gmail_thread_id_from_send
            print(f"    DEBUG: Mapping bot's reply Message-ID '{cleaned_bot_reply_msg_id}' to actual Gmail threadId '{actual_gmail_thread_id_from_send}'")

        log_sent_email(original_sender_email_for_log, receiver_email, msg["Subject"], reply_body_text, html_body, action_type)
        print("✅ Email sent.")
        return True, actual_gmail_thread_id_from_send 
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        print(traceback.format_exc())
        return False, None 

def forward_email_to_human(gmail_service, original_subject, original_body, original_sender, reason_for_forward, gmail_thread_id_to_forward_in=None):
    print(f"📤 Forwarding to human agent: {FORWARD_TO_EMAIL} (Reason: {reason_for_forward})")
    new_subject = f"[ACTION REQUIRED - AI FORWARD] {original_subject}"
    
    # ... (Your HTML and Text prepend logic for the forward reason)
    if "Sender explicitly requested" in reason_for_forward:
        prepend_message_html = f"""<div style="font-family: 'Segoe UI', sans-serif; background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; margin-bottom: 20px; border-radius: 5px;">...</div>""" # (Shortened for brevity)
        prepend_message_text = f"***ACTION REQUIRED: Human Intervention Needed!***\nReason for Forward: {reason_for_forward}\n\n--- Original Message ---\n"
    else:
        prepend_message_html = f"""<div style="font-family: 'Segoe UI', sans-serif; background-color: #e0f7fa; border-left: 5px solid #00bcd4; padding: 15px; margin-bottom: 20px; border-radius: 5px;">...</div>""" # (Shortened for brevity)
        prepend_message_text = f"***AI Could Not Process: Human Review Recommended***\nReason for Forward: {reason_for_forward}\n\n--- Original Message ---\n"
    
    new_body_html = f"{prepend_message_html}<br><br>Sender: {original_sender}<br>Body:<br>{original_body.replace('\n', '<br>')}"
    new_body_text = f"{prepend_message_text}\n\nSender: {original_sender}\nBody:\n{original_body}"
    
    message = MIMEMultipart('alternative')
    message['to'] = FORWARD_TO_EMAIL
    message['from'] = EMAIL_ADDRESS
    message['subject'] = new_subject
    message['Reply-To'] = original_sender
    
    message.attach(MIMEText(new_body_text, 'plain'))
    message.attach(MIMEText(new_body_html, 'html'))
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_to_send_payload = {'raw': raw}

    if gmail_thread_id_to_forward_in:
        message_to_send_payload['threadId'] = gmail_thread_id_to_forward_in

    log_sent_email(original_sender, FORWARD_TO_EMAIL, new_subject, new_body_text, new_body_html, ACTION_FORWARD)

    try:
        gmail_service.users().messages().send(userId='me', body=message_to_send_payload).execute()
        print("✅ Forwarded to human.")
        return True
    except Exception as e:
        print(f"❌ Error forwarding email: {e}")
        return False

def process_email(gmail_service):
    emails_to_process = get_latest_email() 
    if not emails_to_process: return 

    for sender_email, subject, body, msg_object, \
        message_id_header, in_reply_to_header, references_header, \
        segment_thread_id_from_get_latest in emails_to_process:
        
        if EMAIL_ADDRESS.lower() == sender_email.lower() and not is_human_agent_reply(msg_object):
            print(f"⛔ Skipping email from self (not a human agent reply): {subject}")
            continue

        print(f"\n📩 Processing email from {sender_email} with subject: {subject}")
        
        # --- Determine Master Thread ID ---
        master_thread_id = None
        is_first_bot_reply_in_thread = True 

        cleaned_in_reply_to = in_reply_to_header.strip().lstrip('<').rstrip('>') if in_reply_to_header else None
        
        if cleaned_in_reply_to and cleaned_in_reply_to in BOT_REPLY_TO_MASTER_THREAD_MAP:
            master_thread_id = BOT_REPLY_TO_MASTER_THREAD_MAP[cleaned_in_reply_to]
            is_first_bot_reply_in_thread = False 
            print(f"    Found existing Gmail master_thread_id '{master_thread_id}' via BOT_REPLY_MAP.")
        else:
            master_thread_id = segment_thread_id_from_get_latest # Use initial Message-ID or Reference as a temporary key
            print(f"    New/unmapped conversation. Using initial key for history: {master_thread_id}")

        print(f"    Using key for history operations this turn: {master_thread_id}")
        
        actual_bot_reply_for_history = None
        current_thread_history = CONVERSATION_HISTORY.get(master_thread_id, [])
        
        if current_thread_history: print(f"    Retrieved {len(current_thread_history)} history entries for key: {master_thread_id}")
        else: print(f"    No prior history found for key: {master_thread_id}.")
        current_thread_history.append({'role': 'user', 'sender': sender_email, 'content': body})

        if is_human_agent_reply(msg_object):
            print(f"🧠 Detected human agent reply. Extracting feedback...")
            human_ideal_reply, original_context_body = extract_human_reply_and_original_body(msg_object)
            if human_ideal_reply:
                log_ai_feedback(original_context_body or "Original context not fully extracted.", human_ideal_reply)
            # ... (history update logic for human replies can be added here if needed)
            continue
        
        print(f"📧 Processing as customer email from {sender_email} with subject: {subject}")
        
        response_text, action_type, transaction_data = match_template(body, sender_email)
        
        reason_for_forward_override = None
        if get_email_sentiment(body).get('polarity', 0.0) < BOT_REPLY_NEGATIVE_SENTIMENT_THRESHOLD:
            if action_type != ACTION_FORWARD:
                action_type = ACTION_FORWARD 
                reason_for_forward_override = "Very negative sentiment detected in customer email."
        
        email_sent_successfully = False
        newly_established_gmail_thread_id = None 

        if action_type == ACTION_FORWARD:
            final_reason = reason_for_forward_override or "Sender explicitly requested human assistance."
            print(f"📤 Forwarding email. Reason: '{final_reason}'")
            forward_email_to_human(gmail_service, subject, body, sender_email, final_reason, gmail_thread_id_to_forward_in=master_thread_id if not is_first_bot_reply_in_thread else None)
        
        elif action_type == ACTION_REPLY or action_type == ACTION_SECURITY_REPLY:
            email_sent_successfully, newly_established_gmail_thread_id = send_email(
                gmail_service, sender_email, subject, response_text, sender_email, action_type,
                master_thread_id if not is_first_bot_reply_in_thread else None, 
                message_id_header, references_header
            )
            if email_sent_successfully: actual_bot_reply_for_history = response_text
        
        elif action_type == ACTION_LLM_FALLBACK:
            # ... (your logic for find_relevant_cases and building retrieved_case_context_for_llm)
            retrieved_case_context_for_llm = None # Ensure defined
            relevant_cases_found = find_relevant_cases(body, LOADED_CASE_KNOWLEDGE, num_results=1)
            if relevant_cases_found:
                # ... (build context string) ...
                retrieved_case_context_for_llm = "..." # (your logic here)

            llm_reply = generate_reply_with_openrouter(body, retrieved_case_context_for_llm, current_thread_history, transaction_data) 
            
            if llm_reply:
                is_valid_reply, validation_reason = validate_llm_reply(llm_reply)
                if is_valid_reply:
                    print(f"✅ LLM reply passed validation.")
                    email_sent_successfully, newly_established_gmail_thread_id = send_email(
                        gmail_service, sender_email, subject, llm_reply, sender_email, action_type,
                        master_thread_id if not is_first_bot_reply_in_thread else None, 
                        message_id_header, references_header
                    )
                    if email_sent_successfully: actual_bot_reply_for_history = llm_reply
                else: 
                    print(f"❌ LLM reply failed validation ({validation_reason}). Forwarding to human.")
                    forward_email_to_human(gmail_service, subject, body, sender_email, f"LLM reply validation failed ({validation_reason})...", gmail_thread_id_to_forward_in=master_thread_id if not is_first_bot_reply_in_thread else None)
            else: 
                print(f"📤 LLM failed to generate a reply. Forwarding to human.")
                forward_email_to_human(gmail_service, subject, body, sender_email, "AI could not generate a suitable response...", gmail_thread_id_to_forward_in=master_thread_id if not is_first_bot_reply_in_thread else None)
        else:
            print(f"⚠️ Unknown action type: {action_type}. Defaulting to forwarding.")
            forward_email_to_human(gmail_service, subject, body, sender_email, "Unknown bot action type...", gmail_thread_id_to_forward_in=master_thread_id if not is_first_bot_reply_in_thread else None)

        # --- Update Conversation History Store with the correct final Gmail threadId ---
        if master_thread_id:
            final_key_for_history = master_thread_id
            
            if is_first_bot_reply_in_thread and newly_established_gmail_thread_id and newly_established_gmail_thread_id != master_thread_id:
                print(f"    Transitioning history from initial key '{master_thread_id}' to Gmail's threadId '{newly_established_gmail_thread_id}'")
                
                # The history is in current_thread_history, which already includes the user's message
                if actual_bot_reply_for_history:
                    current_thread_history.append({'role': 'assistant', 'sender': BOT_EMAIL, 'content': actual_bot_reply_for_history})
                
                # Re-key the history to the new, definitive Gmail threadId
                CONVERSATION_HISTORY[newly_established_gmail_thread_id] = list(current_thread_history)
                if master_thread_id in CONVERSATION_HISTORY:
                    del CONVERSATION_HISTORY[master_thread_id]
                final_key_for_history = newly_established_gmail_thread_id
            
            elif actual_bot_reply_for_history:
                 current_thread_history.append({'role': 'assistant', 'sender': BOT_EMAIL, 'content': actual_bot_reply_for_history})

            history_to_save = CONVERSATION_HISTORY.get(final_key_for_history, current_thread_history)
            
            if len(history_to_save) > MAX_HISTORY_MESSAGES:
                history_to_save = history_to_save[-MAX_HISTORY_MESSAGES:]
            
            CONVERSATION_HISTORY[final_key_for_history] = history_to_save
            print(f"    Updated history for key '{final_key_for_history}'. Final length: {len(history_to_save)}")


def main_loop(gmail_service):
    """The main operational loop of the bot."""
    while True:
        try:
            process_email(gmail_service)
            print(f"⏳ Waiting {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            print(traceback.format_exc()) 
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing access token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}. Re-running auth flow.")
                # If refresh fails, fall through to re-run the flow
                creds = None # Ensure we re-run the flow
        
        if not creds or not creds.valid: # Check again in case refresh failed
            print("Token is invalid or expired, and refresh failed. Starting new auth flow.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Gmail API service object once at the start
    gmail_service = build('gmail', 'v1', credentials=creds)

    # --- Load all necessary data using the correct function names ---
    print("\n--- Loading Bot Data ---")
    TEMPLATES = load_templates(TEMPLATE_FILE)
    CLEANED_EXAMPLES = load_cleaned_feedback_examples(CLEANED_FEEDBACK_FILE)
    LOADED_CASE_KNOWLEDGE = load_case_knowledge(CASE_KNOWLEDGE_FILE_PATH)
    print("--- Bot Data Loaded ---\n")
    
    # Start the main operational loop of the bot
    main_loop(gmail_service)
        
def main_loop():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Gmail API service object once at the start
    gmail_service = build('gmail', 'v1', credentials=creds)

    while True:
        try:
            # Pass the gmail_service to process_email
            process_email(gmail_service)
            print(f"⏳ Waiting {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Gmail API service object once at the start
    gmail_service = build('gmail', 'v1', credentials=creds)

    # --- NEW: Load cleaned feedback examples here ---
    CLEANED_EXAMPLES = load_cleaned_feedback_examples(CLEANED_FEEDBACK_FILE)

        # --- NEW: Load Case Knowledge ---
    LOADED_CASE_KNOWLEDGE = load_case_knowledge(CASE_KNOWLEDGE_FILE_PATH)
    # --- END NEW ---

    main_loop() # This is where your bot starts its continuous operation
