import json
import os
import re
from collections import Counter
import matplotlib.pyplot as plt # Ensure this is imported
from datetime import datetime, date

# Define paths
LOG_FILE_PATH = "bot_sent_emails.log"
FEEDBACK_LOG_PATH = "novalnet_ai_feedback_cleaned.jsonl" 
BAR_CHART_OUTPUT_PATH = "action_type_bar_chart.png"
PIE_CHART_OUTPUT_PATH = "action_type_pie_chart.png"

# --- load_jsonl_file, get_date_input, filter_entries_by_date_range ---
# --- analyze_bot_sent_logs, analyze_feedback_logs, print_report ---
# (These functions remain the same as in the last complete version I provided,
#  where print_report was simplified for the feedback section. 
#  For brevity, I'm not repeating them here but ensure they are in your script.)

def load_jsonl_file(file_path, file_description="log"):
    entries = []
    if not os.path.exists(file_path):
        print(f"❌ Error: {file_description.capitalize()} file not found at '{file_path}'")
        return entries
    print(f"Attempting to load {file_description} entries from: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Warning: Skipping line {line_number} in {file_description} file due to JSON decode error: {e}")
                        print(f"   Problematic line content: '{line[:100]}...'")
        print(f"✅ Successfully loaded {len(entries)} {file_description} entries.")
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading the {file_description} file: {e}")
    return entries

def get_date_input(prompt_message):
    while True:
        date_str = input(prompt_message + " (YYYY-MM-DD, or press Enter to skip): ").strip()
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD or press Enter to skip.")

def filter_entries_by_date_range(entries, start_date, end_date, timestamp_key="timestamp"):
    if not start_date and not end_date:
        print("ℹ️ No date range provided, processing all entries for this log.")
        return entries
    filtered_entries = []
    if start_date and end_date and start_date > end_date:
        print("⚠️ Warning: Start date is after end date. No entries will be matched for this range.")
        return []
    print(f"Filtering entries from {start_date if start_date else 'beginning'} to {end_date if end_date else 'end'}...")
    for entry in entries:
        timestamp_str = entry.get(timestamp_key)
        if not timestamp_str:
            if start_date or end_date:
                print(f"⚠️ Warning: Entry missing timestamp_key '{timestamp_key}'. Excluding from date-filtered results.")
                continue
            else:
                filtered_entries.append(entry)
                continue
        try:
            entry_date = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").date()
            entry_matches = True
            if start_date and entry_date < start_date:
                entry_matches = False
            if end_date and entry_date > end_date:
                entry_matches = False
            if entry_matches:
                filtered_entries.append(entry)
        except ValueError:
            print(f"⚠️ Warning: Could not parse timestamp '{timestamp_str}' for an entry. Excluding from date-filtered results if filtering active.")
            if not (start_date or end_date):
                 filtered_entries.append(entry)
            continue
    print(f"✅ Found {len(filtered_entries)} entries within the specified date range for this log.")
    return filtered_entries

def analyze_bot_sent_logs(log_entries):
    if not log_entries:
        return {"total_emails": 0, "action_counts": Counter(), "forwarded_email_details": []}
    action_counts = Counter()
    forwarded_email_details = []
    for entry in log_entries:
        action_type = entry.get("bot_action_type")
        if action_type:
            action_counts[action_type] += 1
        if action_type == "FORWARD":
            original_sender = entry.get("original_sender", "N/A")
            forwarded_subject = entry.get("email_subject", "N/A")
            reason_for_forward = "Reason not explicitly logged in body"
            email_body_text = entry.get("email_body_text", "")
            match = re.search(r"Reason for Forward:\s*(.*?)\n", email_body_text, re.IGNORECASE)
            if match:
                reason_for_forward = match.group(1).strip()
            forwarded_email_details.append({
                "original_sender": original_sender,
                "forwarded_subject": forwarded_subject,
                "reason": reason_for_forward
            })
    return {"total_emails": len(log_entries), "action_counts": action_counts, "forwarded_email_details": forwarded_email_details}

def analyze_feedback_logs(feedback_entries):
    if not feedback_entries:
        return {"total_feedback_examples": 0, "sample_feedback_snippets": []}
    sample_feedback_snippets = []
    for i, entry in enumerate(feedback_entries):
        if i < 3:
            snippet = entry.get("original_email_body_cleaned", "N/A")
            sample_feedback_snippets.append(snippet[:150] + "..." if len(snippet) > 150 else snippet)
        else:
            break
    return {"total_feedback_examples": len(feedback_entries), "sample_feedback_snippets": sample_feedback_snippets}

def print_report(bot_sent_analysis_results, feedback_analysis_results, start_date_obj=None, end_date_obj=None):
    print("\n===================================")
    print("   Novalnet AI Bot Email Report")
    if start_date_obj or end_date_obj:
        s_date_str = start_date_obj.strftime('%Y-%m-%d') if start_date_obj else "Beginning"
        e_date_str = end_date_obj.strftime('%Y-%m-%d') if end_date_obj else "Current"
        print(f"    For period: {s_date_str} to {e_date_str}")
    else:
        print("    For period: All Time")
    print("===================================")
    print(f"\n--- Bot Activity (bot_sent_emails.log) ---")
    print(f"Total Bot Actions Logged (in period): {bot_sent_analysis_results['total_emails']}")
    print("\nBreakdown by Bot Action Type:")
    if bot_sent_analysis_results['action_counts']:
        for action_type, count in bot_sent_analysis_results['action_counts'].items():
            print(f"  - {action_type:<20}: {count}")
    else:
        print("  No bot actions recorded for this period.")
    print("\nDetails of Forwarded Emails (from bot_sent_emails.log):")
    if bot_sent_analysis_results['forwarded_email_details']:
        for i, f_email in enumerate(bot_sent_analysis_results['forwarded_email_details'], 1):
            print(f"\n  Forwarded Email #{i}:")
            print(f"    Original Sender   : {f_email['original_sender']}")
            print(f"    Forwarded Subject : {f_email['forwarded_subject']}")
            print(f"    Reason for Forward: {f_email['reason']}") 
    else:
        print("  No emails were forwarded by the bot in this period.")
    print(f"\n--- AI Learning Feedback (novalnet_ai_feedback_cleaned.jsonl) ---")
    print(f"Total Cleaned Feedback Examples (in period): {feedback_analysis_results['total_feedback_examples']}")
    print("\nSample Snippets from Original Customer Emails in Feedback Log (first 3):")
    if feedback_analysis_results['sample_feedback_snippets']:
        for i, snippet in enumerate(feedback_analysis_results['sample_feedback_snippets'], 1):
            print(f"\n  Feedback Customer Email Snippet #{i}:")
            print(f"    \"{snippet}\"")
    else:
        print("  No feedback examples found for this period.")
    print("\n===================================")
    print("         End of Report")
    print("===================================")

def generate_action_type_bar_chart(action_counts, output_path, start_date_obj=None, end_date_obj=None): # Renamed, added dates
    """
    Generates a bar chart of bot action types and saves it to a file.
    """
    if not action_counts:
        print("📊 No action counts to generate a bar chart for bot activity.")
        return

    types = list(action_counts.keys())
    counts = list(action_counts.values())

    if not types:
        print("📊 No action types found in counts to generate a bar chart for bot activity.")
        return

    try:
        plt.figure(figsize=(10, 7)) # Adjusted size slightly for potentially longer title
        bars = plt.bar(types, counts, color=['skyblue', 'lightcoral', 'lightgreen', 'gold', 'plum', 'lightsalmon'])
        
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.05 * (max(counts) if counts else 1), int(yval), ha='center', va='bottom')

        plt.xlabel("Bot Action Type")
        plt.ylabel("Number of Emails")
        
        title = "Novalnet AI Bot - Email Action Types Breakdown"
        if start_date_obj or end_date_obj:
            s_date_str = start_date_obj.strftime('%Y-%m-%d') if start_date_obj else "Start"
            e_date_str = end_date_obj.strftime('%Y-%m-%d') if end_date_obj else "Today"
            title += f"\n({s_date_str} to {e_date_str})"
        plt.title(title)
        
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout() 
        
        plt.savefig(output_path)
        print(f"📊 Bot activity bar chart saved to '{output_path}'")
    except Exception as e:
        print(f"❌ Error generating bot activity bar chart: {e}")

# --- NEW FUNCTION: Generate Pie Chart ---
def generate_action_type_pie_chart(action_counts, output_path, start_date_obj=None, end_date_obj=None):
    """
    Generates a pie chart of bot action types and saves it to a file.
    """
    if not action_counts:
        print("📊 No action counts to generate a pie chart for bot activity.")
        return

    labels = list(action_counts.keys())
    sizes = list(action_counts.values())
    
    if not labels: # If no labels (e.g. action_counts was empty)
        print("📊 No action types found in counts to generate a pie chart.")
        return

    # Explode a slice if desired, e.g., the largest slice or a specific one
    # For now, no explosion, or explode the first slice if it exists
    explode = [0] * len(labels) 
    if sizes and max(sizes) > 0 : # Ensure there's a max value to prevent error on all zeros
        # Optional: explode the largest slice
        # max_index = sizes.index(max(sizes))
        # explode[max_index] = 0.1 
        pass


    try:
        plt.figure(figsize=(10, 8)) # Pie charts often look better a bit larger or more square
        plt.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%',
                shadow=True, startangle=140, 
                colors=['skyblue', 'lightcoral', 'lightgreen', 'gold', 'plum', 'lightsalmon']) # Added some colors
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        
        title = "Novalnet AI Bot - Action Type Proportions"
        if start_date_obj or end_date_obj:
            s_date_str = start_date_obj.strftime('%Y-%m-%d') if start_date_obj else "Start"
            e_date_str = end_date_obj.strftime('%Y-%m-%d') if end_date_obj else "Today"
            title += f"\n({s_date_str} to {e_date_str})"
        plt.title(title)
        
        plt.tight_layout()
        plt.savefig(output_path)
        print(f"📊 Bot activity pie chart saved to '{output_path}'")
    except Exception as e:
        print(f"❌ Error generating bot activity pie chart: {e}")

if __name__ == "__main__":
    print("--- Novalnet AI Bot Report Generator ---")
    start_date_obj = get_date_input("Enter Start Date for report period")
    end_date_obj = get_date_input("Enter End Date for report period")

    all_bot_sent_log_data = load_jsonl_file(LOG_FILE_PATH, "bot activity")
    filtered_bot_sent_data = []
    if all_bot_sent_log_data:
        filtered_bot_sent_data = filter_entries_by_date_range(all_bot_sent_log_data, start_date_obj, end_date_obj, timestamp_key="timestamp")
    
    bot_sent_analysis_results = analyze_bot_sent_logs(filtered_bot_sent_data)

    all_feedback_data = load_jsonl_file(FEEDBACK_LOG_PATH, "feedback")
    filtered_feedback_data = []
    if all_feedback_data:
        filtered_feedback_data = filter_entries_by_date_range(all_feedback_data, start_date_obj, end_date_obj, timestamp_key="timestamp") 
        
    feedback_analysis_results = analyze_feedback_logs(filtered_feedback_data)

    if bot_sent_analysis_results["total_emails"] > 0 or feedback_analysis_results["total_feedback_examples"] > 0:
        print_report(bot_sent_analysis_results, feedback_analysis_results, start_date_obj, end_date_obj)
        
        if bot_sent_analysis_results['action_counts']:
            # Generate and save the bar chart
            generate_action_type_bar_chart(bot_sent_analysis_results['action_counts'], BAR_CHART_OUTPUT_PATH, start_date_obj, end_date_obj)
            # --- NEW: Generate and save the pie chart ---
            generate_action_type_pie_chart(bot_sent_analysis_results['action_counts'], PIE_CHART_OUTPUT_PATH, start_date_obj, end_date_obj)
    else:
        print("No log data found to process for the specified period (or overall).")