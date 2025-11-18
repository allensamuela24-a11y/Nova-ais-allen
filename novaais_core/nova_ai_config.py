# nova_ai_config.py

# --- Reply Validation Configuration ---
BOT_REPLY_NEGATIVE_SENTIMENT_THRESHOLD = -0.1  # Replies should not be more negative than this

UNDESIRABLE_KEYWORDS_IN_REPLY = [
    # --- Overly Casual, Slang, or Too Informal ---
    # Reason: Maintain professionalism and trust. Novalnet handles sensitive financial data.
    "awesome", "cool", "dunno", "gotcha", "gonna", "gotta", "hang on", "hey", "kinda", "sorta",
    "my bad", "no prob", "no worries", "oops", "sup", "whoops", "LOL", "OMG", "BRB", "TTYL", "TBH", "IDK",
    "folks", "guys", "dude", "mate", # Avoid overly familiar terms for customers

    # --- Expressing Excessive Uncertainty or Lack of Confidence (from the bot) ---
    # Reason: The bot should provide clear information or escalate, not sound unsure.
    "i guess", "i think maybe", "i'm not really sure", "i might be wrong", "hard to say",
    "perhaps maybe", "uhh", "umm", "hmm", "could be", "might be", "no clue",
    "as an ai", "i am an ai", "as a language model", # Avoid over-emphasizing AI limitations unless crucial

    # --- Potentially Unprofessional, Minimizing, Flippant, or Patronizing ---
    # Reason: Customer issues are serious. Avoid sounding dismissive or condescending.
    "whatever", "anyways", "just a", "obviously", "actually", # 'Actually' can sound corrective
    "literally", "basically", "you see", "believe me", "relax", "calm down",
    "it's not a big deal", "deal with it", "frankly", "to be honest",

    # --- Words that Could Cause Undue Alarm or are Too Negative if Misused by Bot ---
    # Reason: Be precise, calm, and avoid hyperbole.
    "catastrophic", "doomed", "impossible", # "Failure" is okay if used factually, e.g., "payment failure"
    "terrible", "horrible", "awful", # Bot shouldn't use these to describe situations

    # --- Accusatory or Blaming Language ---
    # Reason: Maintain a supportive and problem-solving tone.
    "you should have", "you failed to", "it's your fault", "you didn't", "wrong", # Rephrase these more constructively

    # --- Over-promising or Absolute Statements ---
    # Reason: Avoid making commitments the bot can't ensure.
    "always", "never", "instantly", "guarantee", "promise", "perfect", "flawless", "definitely", "certainly", # Use with caution, only if true

    # --- Internal Jargon or Unhelpful Process References ---
    # Reason: Customers don't need to know internal specifics that don't help them.
    "backend", "frontend", "our devs", "internal ticket", "SOP", "escalation matrix", "jira",
    "our internal policy states", # Rephrase as "Our process..." or "For security reasons..."

    # --- Placeholder/Test Words ---
    "test_string", "placeholder_text", "[IGNORE]", "[TODO]", "dummy_data", "lorem ipsum",
    "[customer_name]", "[transaction_id_placeholder]", # Examples of unfilled placeholders

    # --- Generic "bad" words (LLM likely filters, but good to have a few examples) ---
    "stupid", "lame", "dumb", "crap", "idiot"
]

EXPECTED_SIGNATURE_PART = "Novalnet Support" 

MIN_REPLY_WORD_COUNT = 10     # Replies should have at least this many words
MAX_REPLY_WORD_COUNT = 250    # Replies shouldn't be excessively long (adjust as needed)
MAX_ALL_CAPS_WORD_LENGTH = 3  # Words longer than this shouldn't be in ALL CAPS (e.g., "HELP" is okay, "IMPORTANT" is not)