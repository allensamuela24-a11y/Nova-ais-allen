import json
import os
import re

def read_feedback_log(log_file_path):
    """
    Reads the AI feedback log file (JSON Lines format) and yields each parsed entry.
    """
    if not os.path.exists(log_file_path):
        print(f"Error: Log file not found at '{log_file_path}'")
        return

    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip() 
            if not line: 
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} in line: '{line}' (line number: {line_number})")
                continue

def _normalize_whitespace(text):
    """
    Standardizes newlines and multiple spaces.
    """
    if not isinstance(text, str):
        return ""
    text = text.replace('\r\n', '\n').replace('\r', '\n') 
    text = re.sub(r'[ \t]+', ' ', text) 
    text = re.sub(r'\n{3,}', '\n\n', text) 
    text = text.strip() 
    return text

def clean_common_artifacts(text):
    """
    Removes artifacts common to emails (e.g., '>' for quoted text).
    """
    if not isinstance(text, str):
        return ""
    old_text = ""
    # Iteratively remove leading '>' to handle multiple levels of quoting
    while old_text != text: 
        old_text = text
        text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE).strip()
    return text

def clean_original_email_body_specifics(text_input_after_quote_removal):
    """
    Specifically cleans the 'original_email_body' from ai_learning_feedback.log.
    This body is often the content of the email forwarded to the human agent,
    so it might contain the bot's forwarding headers before the actual customer message.
    Aims to extract only the actual customer's message.
    Assumes 'text_input_after_quote_removal' has had leading '>' removed.
    """
    if not isinstance(text_input_after_quote_removal, str):
        return ""

    cleaned_text = text_input_after_quote_removal
    
    # Define the marker that your bot adds before the original customer message details
    original_message_marker = "--- Original Message ---"
    marker_pos = cleaned_text.find(original_message_marker)

    if marker_pos != -1:
        # If the marker is found, focus on the text *after* it
        content_after_marker = cleaned_text[marker_pos + len(original_message_marker):]
        
        # Now, look for "Body:" preceded by "Sender:" within this content_after_marker
        # The (?s) flag makes . match newlines as well.
        body_match = re.search(r"Sender:.*?\nBody:\s*(.*)", content_after_marker, re.IGNORECASE | re.DOTALL)
        if body_match:
            # If "Body:" is found, extract the content after it
            customer_message = body_match.group(1).strip()
            # print(f"    DEBUG (clean_original_email_body_specifics): Found 'Body:', extracted: '{customer_message[:100]}...'")
            return customer_message
        else:
            # If "Sender:... Body:..." structure is not found after the marker,
            # it might be that the 'original_email_body' in the log was structured differently
            # or was already partially cleaned. As a fallback, return the text after the marker.
            # print(f"    DEBUG (clean_original_email_body_specifics): Found '--- Original Message ---', but not 'Sender/Body' structure after. Using text after marker: '{content_after_marker[:100]}...'")
            return content_after_marker.strip()
    else:
        # If "--- Original Message ---" is not found at all,
        # the input text might be a direct customer email (not a forwarded one)
        # or one of the "Original context not fully extracted." messages.
        # In this case, we assume it's already relatively clean or can't be further stripped by this logic.
        # print(f"    DEBUG (clean_original_email_body_specifics): No '--- Original Message ---' marker. Text passed through: '{cleaned_text[:100]}...'")
        return cleaned_text

def clean_human_ideal_reply_specifics(text):
    """
    Applies cleaning specific to the 'human_ideal_reply'.
    Focuses on removing signatures or other non-essential trailing parts.
    """
    if not isinstance(text, str):
        return ""
    
    # Remove common Novalnet signatures/footers that might be part of the human reply
    signatures_to_remove = [
        r'Novalnet Support Team', r'Novalnet Corporate Communications',
        r'Novalnet Strategic Communications', r'Novalnet Corporate Affairs',
        r'^\s*Allen\s*$', 
        r'Mit freundlichen Grüßen\s*Ihr Payment-Team der Novalnet AG',
        r'Best regards,\s*Novalnet Support'
        # Add more specific signature patterns if needed
    ]
    cleaned_text = text
    for signature_pattern in signatures_to_remove:
        cleaned_text = re.sub(r'\s*' + signature_pattern + r'\s*$', '', cleaned_text, flags=re.MULTILINE | re.IGNORECASE).strip()
    
    # Remove trailing "ACTION REQUIRED" or "AI Could Not Process" blocks if they were copied into the human reply
    trailing_bot_noise_patterns = [
        r'\s*[\U0001F6A8\U0001F916].*?(?:ACTION REQUIRED|AI Could Not Process|Human Review Recommended):.*?$', # Matches the header line
        r'\s*\*Reason for Forward:\*.*$' # Matches the reason line
    ]
    for pattern in trailing_bot_noise_patterns:
         # This will remove these patterns if they are at the very end of the text, possibly after some whitespace.
        cleaned_text = re.sub(pattern + r'\s*$', '', cleaned_text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE).strip()
        # Try also removing if they are just before a signature that was already removed
        cleaned_text = re.sub(r'\s*' + pattern, '', cleaned_text, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE).strip()


    return cleaned_text

def clean_text(text, is_original_email_body=False):
    """
    Main cleaning function that applies appropriate cleaning based on content type.
    """
    if not isinstance(text, str):
        return ""
    
    # 1. Initial normalization (handles \r, multiple spaces/newlines, leading/trailing whitespace)
    normalized_text = _normalize_whitespace(text)
    
    # 2. Remove common quoting artifacts (like '>') BEFORE specific cleaning
    text_no_quotes = clean_common_artifacts(normalized_text)
    
    # 3. Apply content-specific cleaning
    if is_original_email_body:
        cleaned_specific_text = clean_original_email_body_specifics(text_no_quotes) 
    else: 
        cleaned_specific_text = clean_human_ideal_reply_specifics(text_no_quotes)

    # 4. One final pass of common artifact cleaning and normalization
    final_cleaned_text = clean_common_artifacts(cleaned_specific_text) # Clean quotes again
    final_text = _normalize_whitespace(final_cleaned_text)
    
    return final_text

if __name__ == "__main__":
    log_file = "ai_learning_feedback.log" # Your raw feedback log
    output_file = "novalnet_ai_feedback_cleaned.jsonl" 

    print(f"--- Reading and CLEANING '{log_file}' ---")
    cleaned_entries = [] 

    for entry_num, entry in enumerate(read_feedback_log(log_file), 1):
        original_body_raw = entry.get('original_email_body', '')
        human_reply_raw = entry.get('human_ideal_reply', '')

        # Clean the original body to get the customer's actual message for few-shot
        cleaned_customer_body = clean_text(original_body_raw, is_original_email_body=True)
        
        # Clean the human ideal reply
        cleaned_human_reply = clean_text(human_reply_raw, is_original_email_body=False)

        if not cleaned_customer_body.strip() and not human_reply_raw.strip():
            print(f"Warning: Both cleaned original email body and raw human reply are empty for entry timestamp {entry.get('timestamp')} (Entry #{entry_num}). Skipping.")
            continue
        # If customer body became empty after cleaning but human reply exists, it's still a valid feedback pair.
        # The "Original context not fully extracted." entries in your log are an example.
        elif not cleaned_customer_body.strip() and human_reply_raw.strip(): 
             if "Original context not fully extracted." not in original_body_raw : # only print warning if it wasn't already this
                print(f"Warning: Cleaned original email body (customer part) is empty for entry timestamp {entry.get('timestamp')} (Entry #{entry_num}). Input was: '{original_body_raw[:200]}...'. This might be an issue with cleaning or the logged data.")
             # We keep the original_body_raw (normalized) if cleaning results in empty, to preserve "Original context not fully extracted." messages
             cleaned_customer_body = _normalize_whitespace(original_body_raw) if "Original context not fully extracted." in original_body_raw else "Original context could not be cleaned effectively."


        cleaned_entry = {
            "timestamp": entry.get("timestamp"),
            "original_email_body_cleaned": cleaned_customer_body,
            "human_ideal_reply_cleaned": cleaned_human_reply
        }
        cleaned_entries.append(cleaned_entry)

    print(f"\nTotal cleaned entries to be saved: {len(cleaned_entries)}")

    print(f"--- Saving cleaned data to '{output_file}' ---")
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            for entry in cleaned_entries:
                json.dump(entry, outfile, ensure_ascii=False)
                outfile.write('\n')
        print(f"Successfully saved {len(cleaned_entries)} cleaned entries to '{output_file}'.")
    except IOError as e:
        print(f"Error saving cleaned data to file: {e}")

    print("Cleaning and saving process complete.")