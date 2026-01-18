import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging
import re

# ================= CONFIG =================
URL_BASE = "https://www.itinerarinellarte.it"
URL_EVENTI = f"{URL_BASE}/it/mostre/friuli-venezia-giulia"

GIORNI_AVANTI = 7
MAX_PAGES = 4
SLEEP_TIME = 2

SHEET_NAME = "Eventi in Friuli"
WORKSHEET_NAME = "Itinerarinellarte"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MESI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

# ================= UTILS =================
def parse_data(data_str):
    """Estrae una data dd/mm/yyyy se presente"""
    if not data_str:
        return None
    match = re.search(r"\d{2}/\d{2}/\d{4}", data_str)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(), "%d/%m/%Y")
    except ValueError:
        return None

# ================= SCRAPING =================
def estrai_eventi(soup):
    eventi = []

    oggi = datetime.now()
    limite = oggi + timedelta(days=GIORNI_AVANTI)

    for evento in soup.select("a.row-tile"):
        # -------- TITOLO --------
        titolo_elem = evento.find("h3")
        titolo = titolo_elem.get_text(strip=True) if titolo_elem else "Titolo non disponibile"

        # -------- LINK --------
        link = evento.get("href", "")
        if link.startswith("/"):
            link = f"{URL_BASE}{link}"

        # -------- LUOGO --------
        luogo = "Luogo non disponibile"
        luogo_elem = (
            evento.select_one("span.eventi-luogo")
            or evento.select_one("div.eventi-date span")
        )
        if luogo_elem:
            luogo = luogo_elem.get_text(strip=True)

        # -------- DATE --------
        date_elems = evento.select("span.eventi-data")
        if len(date_elems) < 2:
            logging.warning(f"Date mancanti per evento: {titolo}")
            continue

        data_inizio = parse_data(date_elems[0].get_text())
        data_fine = parse_data(date_elems[1].get_text())

        if not data_inizio or not data_fine:
            logging.warning(f"Formato data non valido: {titolo}")
            continue

        data_inizio = max(data_inizio, oggi)
        data_fine = min(data_fine, limite)

        # -------- ESPANSIONE GIORNI --------
        for i in range((data_fine - data_inizio).days + 1):
            giorno = data_inizio + timedelta(days=i)
            eventi.append({
                "titolo": titolo,
                "data": f"{giorno.day:02d} {MESI[giorno.month]} {giorno.year}",
                "data_sort": giorno,
                "ora": "Ora non disponibile",
                "luogo": luogo,
                "link": link,
                "categoria": "Mostre"
            })

    return eventi

# ================= MAIN =================
def main():
    # -------- GOOGLE SHEETS AUTH --------
    try:
        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",
            "private_key_id": os.getenv("GSHEET_PRIVATE_KEY_ID"),
            "private_key": os.getenv("GSHEET_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("GSHEET_CLIENT_EMAIL"),
            "client_id": os.getenv("GSHEET_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": (
                "https://www.googleapis.com/robot/v1/metadata/x509/"
                + os.getenv("GSHEET_CLIENT_EMAIL")
            )
        }

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            credentials_info, scope
        )
        client = gspread.authorize(credentials)
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)

        logging.info("Accesso a Google Sheets riuscito")
    except Exception as e:
        logging.error(f"Errore Google Sheets: {e}")
        return

    # -------- PULIZIA FOGLIO (ROBUSTA) --------
    try:
        rows = sheet.row_count
        if rows > 1:
            sheet.delete_rows(2, rows)
            logging.info("Righe precedenti eliminate")
        else:
            logging.info("Nessuna riga da eliminare")
    except Exception as e:
        logging.error(f"Errore pulizia foglio: {e}")
        return

    # -------- SCRAPING --------
    eventi_totali = []

    for page in range(MAX_PAGES + 1):
        url = URL_EVENTI if page == 0 else f"{URL_EVENTI}?page={page}"
        logging.info(f"Scraping pagina {page}")

        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            r.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Errore richiesta pagina {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        eventi = estrai_eventi(soup)
        if not eventi:
            break

        eventi_totali.extend(eventi)
        time.sleep(SLEEP_TIME)

    # -------- UPLOAD --------
    if not eventi_totali:
        logging.info("Nessun evento trovato")
        return

    eventi_totali.sort(key=lambda e: e["data_sort"])

    righe = [
        [e["titolo"], e["data"], e["ora"], e["luogo"], e["link"], e["categoria"]]
        for e in eventi_totali
    ]

    sheet.append_rows(righe)
    logging.info(f"{len(righe)} eventi caricati su Google Sheets")

# ================= START =================
if __name__ == "__main__":
    main()
