import json

# Data manually segmented from your provided column-wise pastes.
# I've done my best to interpret multi-line entries for a single case.
# Please review a few entries in the output for accuracy.

list_col_A_case_title = [
    "Kündigung", "Anzeige", "Bereits gekündigt", "Betrug", "Warum wurde abgebucht", "Blackliste",
    "Polizei/Staatsanwaltschaft", "Bankanfrage Rückruf der Zahlung", "Rechnungskopie", "Neue Bankdaten",
    "Neue Kreditkarte", "SWM App nicht nutzbar", "Storrno der Buchung oder Bestellung", "DSGVO", "DSGVO",
    "Schuldenbereinigung", "Widerruf der Buchung oder Bestellung", "Keine Ware erhalten", "Inkasso",
    "Bankanfrage SEPA", "Zahlung erhalten", "Insolvenz", "Betreuer", "SEPA Lastschrift erneut buchen",
    "Doppelzahlung", "Händler Insolvenz", "Ablöse Ratenzahlung", "SWM warum müssen RLS Kosten gezahlt werden",
    "Direktzahlung", "Inkasso unberechtigt", "Neuer Abbuchungstermin", "Bankdaten zur Zahlung",
    "Forderung abweichend", "Rechtsanwalt E-Mails", "Beleg anfordern", "Zahlungsbeleg", "spätere Zahlung",
    "Neue Daten", "Fragen zur Abrechnung oder dem CRM", "Minderjährigkeit", "Todesfall",
    "Anfragen zur Zusammenarbeit", "Bankanfragen Fehlerprotokoll", "Neuer Name", "Spezifische SWM-anfragen"
]

list_col_B_detailed_explanation = [
    "Der Endkunde wünscht die Kündigung seines ABO oder der Dienstleistung",
    "Der Endkunde hat eine Anzeige erstattet",
    "Der Endkunde hat bereits gekündigt aber eine weitere Abbuchung",
    "Die Daten des Endkunden wurde missbraucht, er hat keine Bestellung gemacht",
    "Der Endkunde kennt den Grund der Abbuchung oder die Novalnet nicht",
    "Der Endkunde entzieht das SEPA Lastschriftsmandat",
    "Die Polizei sendet uns ein Ermittlungsersuchen",
    "Ein Endkunde fordert eine Zahlung über die Bank zurück",
    "Der Endkunde wünscht eine Kopie der Rechnung",
    "Der Endkunde hat eine neue Bankverbindung",
    "Der Kunde hat einen neue Kreditkarte",
    "Der Kunde kann nicht über die App buchen",
    "Der Endkunde möchte seine Bestellung stornieren",
    "Der Endkunde wünscht eine Löschung der Daten und/oder Kündigung",
    "Der Endkunde wünscht eine Auskunft über die gespeicherten Daten",
    "Der Endkunde möchte seine Schulden abzahlen",
    "Der Endkunde möchte seine Bestellung widerrufen",
    "Der Endkunde hat keine Ware oder Dienstleisteung erhalten",
    "Der Endkunde ist beim Inkasso",
    "Anforderung einen SEPA Mandates", # Intentionally kept as is from paste
    "Der Endkunde fragt ob seine Forderung beglichen ist",
    "Der Endkunde ist Zahlungsunfähig",
    "Der Endkunde steht unter Betreuung/Vormundschaft",
    "Der Endkunde wünscht eine erneute Abbuchung",
    "Der Endkunde hat die Forderung doppelt gezahlt",
    "Ein Vertragspartner ist Insolvent",
    "Der Endkunde wünscht eine sofortige Ablöse der Ratenzahlung",
    "Der Kunde bemengelt die Kosten der Rücklastschrift",
    "Der Endkunde hat direkt an den Vertragspartner gezahlt",
    "Der Endkunde hat gezahlt, die Zahlung ist aber nicht verbucht",
    "Der Endkunde wünscht ein neues Datum zum Einzug der SEPA Lastschrift",
    "Der Endkunde wünscht eine Bankverbindung zur Belgeichung einer Forderung (vor Inkassoübergabe)",
    "Der Endkunde hat einen anderen € Betrag in der Rechnung",
    "Der Endkunde hat kein Lastschriftmandat erteilt, kennt Novalnet nicht und möchte keine Abbuchung von seinem Konto zulassen. (z.B. Werdermann)",
    "Der Endkunde sagt er hat gezahlt ohne Beleg, Zahlung ist nicht verbucht",
    "Der Endkunde sendet einen Zahlungsbeleg",
    "Der Endkunde wünscht ein späteres Zahlungsziel",
    "Der Endkunde hat eine neue E-Mail oder Postanschrift",
    "Vertragspartner hat Fragen zur Auszahlung oder zu unserem System",
    "Der Endkunde ist Minderjährig",
    "Der Endkunde ist verstorben",
    "Jemand möchte mit Novalnet einen Vertrag schließen",
    "Die Bank sendet uns ein Protokoll mit Fehlermeldungen per Fax",
    "Der Endkunde hat einen neuen Namen (Hochzeit)",
    "einzelne Fragen"
]

list_col_C_todo = [
    "Nachricht über CRM an Vertragspartner, CC Endkunde verschicken",
    "Blacklist Eintrag im Admin, Nachricht an den Vertragspartner, CC Endkunde verschicken",
    "Nachricht an den Vertagsprtner über Outlook weiterleiten", # Typo 'Vertagsprtner' kept as is from paste
    "Nachricht an Endkunde über CRM verschicken",
    "Nachricht über CRM an Endkunde verschicken",
    "Blacklist Eintrag im Admin, Nachricht über CRM an Vertragspartner, CC Endkunde verschicken",
    "Blacklist Eintrag im Admin, Einstellung der offenen Forderungen, Erstellen des Antwortfaxes im CRM, Beantwortung an die Dienststellle per FAX",
    "Nachricht über CRM an Vertragspartner verschicken",
    "Nachricht über CRM an Vertragspartner, CC Endkunde verschicken",
    "Bankdaten im CRM abändern oder weiterleiten an den Vertragspartner (bei SWM Link über CRM verschicken)",
    "Nachricht über CRM an endkunden verschicken",
    "Nachricht über CRM an SVEA verschicken",
    "Weiterleitung der Nachricht über Outlook an den Vertragspartner",
    "Blacklisten, Nachricht über CRM (DATENSCHUTZ nicht Payment) an Endkunde, Vertragspartner und Datenschutz@novalnet verschicken",
    "Nachricht an Endkunde über CRM verschicken",
    "Nachricht an den Vertragspartner und Inkassodienstleister weiterleiten",
    "Weiterleitung der Nachricht über Outlook an den Vertragspartner",
    "Nachricht über CRM an Vertragspartner, CC Endkunde verschicken",
    "Nachricht an Endkunde verschicken mit den Daten des Dienstleisters",
    "Nachricht über CRM an Vertragspartner verschicken",
    "Nachricht über CRM an Endkunde, CC Vertragspartner verschicken",
    "Blacklist Eintrag im Admin, Nachricht an den Vertragspartner und Inkassodienstleister weiterleiten",
    "Blackliste (nur wenn in der Vollmacht Vermögenssorge steht), Weiterleitung über Outlook an den Vertragspartner",
    "Nachricht über CRM an Endkunden verschicken",
    "Weiterleitung der Nachricht über Outlook an den Vertragspartner, Bitte um Erstattung an den Endkunden",
    "Weiterleitung der Nachricht an Buchhaltung der Novalnet, und Antwort von Buhu an den Endkunden kommunizieren",
    "Weiterleiten an Buchhaltung@novalnet wegen Ablösesumme, Ablösesumme mit Bankdaten an Endkunde verschicken",
    "Nachricht über Outlook an den Endkunden verschicken (Vorlage aus dem Handbuch)",
    "Weiterleitung über CRM an Vertragspartner, CC Endkunde", # Assuming 'Kope' was 'Endkunde' or similar based on context
    "Beleg der Zahlung anfordern vom Endkunden und an Collection@novelnet mit bitte um Einstellung der Forderung verschicken", # Typo 'novelnet' kept
    "Weiterleitung an Buchhaltung@novalnet",
    "Nachricht über CRM an Endkunde verschicken",
    "Weiterleitung der Nachricht an Vertragspartner",
    "Nachricht über CRM und Outlook verschicken, Endkunden auf die Blacklist setzen, E-Mail an den Rechtsanwalt senden.",
    "Nachricht an Endkunde über CRM verschicken",
    "Geldeingang prüfen im Pool, evtl. über Matching@novalnet finden und buchen lassen, Nachricht über CRM an Vertragspartner, CC Endkunde verschicken",
    "Im Admin Forderung aussetzen, Vorsicht geht nicht bei Zahlungsgarantie",
    "Im Admin abändern und Endkunden über Outlook die Änderung bestätigen, Vertragspartner in CC",
    "Weiterleitung an Support@novalnet",
    "Blacklist Eintrag im Admin, Nachricht an den Vertragspartner, CC Endkunde verschicken",
    "Sterbeurkunde anfordern, Blacklisten und an Vertragspartner weiterleiten",
    "Weiterleitung an Sales@novalnet",
    "Weiterleitung an AH@Novalnet und CC JR@Novalnet über Outlook",
    "Weiterleitung JR@Novalnet über Outlook",
    "personalisiert auf die Frage"
]

list_col_D_email_action_type = [
    "Externe Weiterleitung\nmit Endkunde auf Kopie",
    "Mehrere Schritte\n1. Blacklist Eintrag\n2. Händler informieren mit\nEndkunde auf Kopie",
    "Externe Weiterleitung\nHändler informieren mit Endkunde auf Kopie",
    "Antwortemail",
    "Antwortemail",
    "Mehrere Schritte\n1. Blacklist Eintrag\n2. Händler informieren mit Endkunde auf Kopie",
    "Mehrere Schritte\n1. Eintrag in die Blacklist\n2. Einstellung der offenen Forderungen\n3. Erstellung eines Reports\n4. Beantwortung an die Dienststelle",
    "Externe Weiterleitung:\nHändler informieren",
    "Externe Weiterleitung:\nHändler informieren mit Endkunde auf Kopie",
    "Mehrere Schritte\n1. Änderung der Bankdaten\n2. Den Link für Aktualisierung vershicken\n3. Händler informieren",
    "Antwortemail",
    "Externe Weiterleitung:\nSVEA/Inkassopartner informieren",
    "Externe Weiterleitung",
    "Mehrere Schritte\n1. Eintrag in die Blacklist\n2. Endkunde informieren mit den Händler auf Kopie (VON DATENSCHUTZ)",
    "Antwortemail",
    "Extern Weiterleitung:\nHändler und SVEA/Inkassopartner informieren",
    "Externe Weiterleitung:\nHändler informieren mit Endkunde auf Kopie",
    "Externe Weiterleitung:\nHändler informieren mit Endkunde auf Kopie",
    "Antwortemail",
    "Externe Weiterleitung",
    "Antwortemail\nmit Händler auf Kopie",
    "Mehrere Schritte\n1. Blacklist Eintrag\n2. Weiterleitung an Händler und SVEA/Inkassopartner",
    "Mehrere Schritte\n1. Blacklist Eintrag\n2. Weiterleitung an Händler mit Endkunde auf Kopie",
    "Antwortemail",
    "Externe Weiterleitung",
    "Interne Weiterleitung",
    "Mehrere Schritte\n1. Interne Weiterleitung\n2. Antwortemail",
    "Antwortemail",
    "Externe Weiterleitung\nmit den Händler auf Kope", # Typo 'Kope' kept
    "Mehrere Schritte\n1. Beleg anfordern\n2. Interne Weiterleitung",
    "Interne Weiterleitung",
    "Antwortemail",
    "Externe Weiterleitung\nmit Endkunde auf Kopie",
    "Mehrere Schritte\n1. Eintrag in die Blacklist\n2. Händler informieren\n3. Antwortemail",
    "Antwortemail",
    "Mehrere Schritte\n1. Interne Weiterleitung\n2. Antwortemail",
    "Mehrere Schritte\n1. Frist wenn möglich verlängern\n2. Antwortemail",
    "Mehrere Schritte\n1. Adresse ändern\n2. Antwortemail mit den Händler auf Kopie",
    "Interne Weiterleitung",
    "Mehrere Schritte\n1. Blacklist Eintrag\n2. Händler informieren mit\nEndkunde auf Kopie",
    "Mehrere Schritte\n1. Antwortemail\n2. Sterbeurkunde anfordern\n3. Händler informieren",
    "Interne Weiterleitung",
    "Interne Weiterleitung",
    "Interne Weiterleitung",
    "Mehrere Schritte\nWeiterleitung oder Antwortemail"
]

list_col_E_priority = [
    "1", "1", "1", "1", "2", "2", "2", "3", "3", "3", "3", "3", "4", "4", "4", "5", "5", "5", "6", "6",
    "6", "6", "7", "7", "7", "7", "8", "8", "9", "9", "9", "10", "10", "11", "12", "12", "13", "13", "14",
    "14", "14", "15", "15", "16", "17"
]

list_col_F_prozentsatz = [
    "20%", "20%", "20%", "15%", "10%", "10%", "10%", "10%", "10%", "10%", "10%", "10%", "10%", "10%", "10%",
    "10%", "10%", "10%", "10%", "10%", "10%", "8%", "6%", "5%", "5%", "5%", "5%", "5%", "5%", "5%", "5%",
    "5%", "5%", "5%", "5%", "5%", "5%", "4%", "4%", "4%", "3%", "3%", "3%", "2%", "2%"
]

list_col_G_template_snippet = [
    "Ihr Kunde möchte Kündigen", "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung", "Betrug behauptet",
    "Information zur Transaktion", "Entzug der Einzugsermächtigung", "Erstelt übr die CRM\nFax nach Polizei",
    "Rückruf der Zahlung", "Ihr Kunde wünscht eine Rechnungskopie", "Aktualisierung Ihrer Zahlungsdaten im Mlogin",
    "Aktualisierung Ihrer Zahlungsdaten", "Prüfung und Freischaltung", "1_Bitte um Bearbeitung",
    "Ihre Löschanfrag gem. Art. 17 DS-GVO und Kündigung und Löschanfrag gem. Art. 17 DS-GVO",
    "Infomation zur Transaktion", # Typo 'Infomation' kept
    "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung", "Nichterhalt der Ware/Dienstleistung",
    "6_Der Endkunde ist beim Inkasso", "Anforderung SEPA- Mandat", "Ihre Zahlung ist bei uns eingegangen",
    "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung",
    "Bankdaten der Novalnet (mit dem Zusatz: Leider ist einen erneute Abbuchung nicht möglich, bitte tätigen Sie einen SEPA Überweisung)",
    "Bitte um Erstattung an den Endkunden", "1_Bitte um Bearbeitung", "Bankdaten der Novalnet",
    "8_Offene Forderung und Rücklastschriftgebühren", "Direktzahlung Endkunde",
    "Fehlender Zahlungnachweis", # Typo 'Zahlungnachweis' kept
    "1_Bitte um Bearbeitung", "Bankdaten der Novalnet", "1_Bitte um Bearbeitung",
    "Informationen zu Ihrer Transaktion\nEntzug der Einzugsermächtigung\n11_E-Mail an den Rechtsanwalt",
    "Fehlender Zahlungnachweis", "Ihre Zahlung bei uns eingegangen",
    "13_Verlängerungszahlungsziel alles außer Zahlungsgarantie\n\nbeim Zahlungsgarantie - schicken wir Template Bankdaten Novalnet mit dem Satz dazu (leider kann das zahlungsziel nicht verlengärt werden)",
    "13_Datenaktualisirung", # Typo 'Datenaktualisirung' kept
    "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung", "Entzug der Einzugsermächtigung",
    "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung", "1_Bitte um Bearbeitung", "siehe SWM vorlagen"
]

list_col_H_actions_code = [
    "2", "1", "2", "3", "5", "1", "1", "3", "6", "7", "8", "9", "2", "1", "5", "10", "2", "11", "12", "13",
    "14", "1", "1", "15", "1", "1", "1", "16", "17", "1", "1", "18", "1", "1", "19", "1", "1", "1", "1",
    "1", "1", "1", "1", "1", "1"
]

# Check consistency
if not (len(list_col_A_case_title) == 45 and \
        len(list_col_B_detailed_explanation) == 45 and \
        len(list_col_C_todo) == 45 and \
        len(list_col_D_email_action_type) == 45 and \
        len(list_col_E_priority) == 45 and \
        len(list_col_F_prozentsatz) == 45 and \
        len(list_col_G_template_snippet) == 45 and \
        len(list_col_H_actions_code) == 45):
    print("Error: One or more column lists do not have exactly 45 entries. " \
          "Please check the manual data segmentation above. Outputting partial or no JSONL content.")
else:
    print("All column lists have 45 entries. Proceeding to generate JSONL content.\n")
    jsonl_output_lines = []
    for i in range(45):
        try:
            priority_val = int(list_col_E_priority[i].strip())
            frequency_val = int(list_col_F_prozentsatz[i].strip().replace('%',''))
            action_code_val = int(list_col_H_actions_code[i].strip())

            case_obj = {
                "case_title": list_col_A_case_title[i].strip(),
                "detailed_explanation_de": list_col_B_detailed_explanation[i].strip(),
                "todo_de": list_col_C_todo[i].strip(),
                "email_action_type_de": list_col_D_email_action_type[i].strip(),
                "priority": priority_val,
                "frequency_percent": frequency_val,
                "template_snippet_name_de": list_col_G_template_snippet[i].strip(),
                "action_code": action_code_val,
                "match_keywords_de": [], # Placeholder for German keywords
                "match_keywords_en": []  # Placeholder for English keywords
            }
            jsonl_output_lines.append(json.dumps(case_obj, ensure_ascii=False))
        except IndexError:
            error_msg = f'{{"error": "Data missing for constructing case {i+1}. Index out of range."}}'
            jsonl_output_lines.append(error_msg)
            print(f"Error: Data missing for constructing case {i+1}. Index out of range.")
        except ValueError as ve:
            error_msg = f'{{"error": "ValueError for case {i+1}: {ve}. Prio=\'{list_col_E_priority[i]}\', Freq=\'{list_col_F_prozentsatz[i]}\', ActionCode=\'{list_col_H_actions_code[i]}\'"}}'
            jsonl_output_lines.append(error_msg)
            print(f"Error: ValueError for case {i+1}: {ve}")
        except Exception as e:
            error_msg = f'{{"error": "Unexpected error for case {i+1}: {e}"}}'
            jsonl_output_lines.append(error_msg)
            print(f"Error: Unexpected error for case {i+1}: {e}")


    final_jsonl_content = "\n".join(jsonl_output_lines)

    print("--- Start of novalnet_case_knowledge.jsonl content ---")
    print(final_jsonl_content)
    print("--- End of novalnet_case_knowledge.jsonl content ---")