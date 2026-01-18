import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging
import re

# ---------------- CONFIG ----------------
URL_BASE = "https://www.itinerarinellarte.it"
URL_EVENTI = f"{URL_BASE}/it/mostre/friuli-venezia-giulia"

GIORNI_AVANTI = 7
MAX_PAGES = 4
SLEEP_TIME = 2

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MESI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

# ---------------- UTILS ----------------
def parse_data(data_str):
    """Estrae una data nel formato dd/mm/yyyy se presente"""
    match = re.search(r"\d{2}/\d{2}/\d{4}", data_str)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(), "%d/%m/%Y")
    except ValueError:
        return None


# ---------------- SCRAPING ----------------
def estrai_eventi(soup):
    eventi = []

    oggi = datetime.now()
    limite = oggi + timedelta(days=GIORNI_AVANTI)

    for evento in soup.select("a.row-tile"):
        # ---- titolo ----
        titolo_elem = evento.find("h3")
        titolo = titolo_elem.get_text(strip=True) if titolo_elem else "Titolo non disponibile"

        # ---- link ----
        link = evento.get("href", "")
        if link.startswith("/"):
            link = f"{URL_BASE}{link}"

        # ---- luogo ----
        luogo = "Luogo non disponibile"
        luogo_elem = evento.select_one("span.eventi-luogo") \
                     or evento.select_one("div.eventi-date span")
        if luogo_elem:
            luogo = luogo_elem.get_text(strip=True)

        # ---- date ----
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

        # ---- crea eventi per ogni giorno ----
        delta = (data_fine - data_inizio).days
        for i in range(delta + 1):
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


# ---------------- MAIN ----------------
def main():
    # ---- Google Sheets ----
    try:
        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",
            "private_key": os.getenv("GSHEET_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("GSHEET_CLIENT_EMAIL"),
            "token_uri": "https://oauth2.googleapis.com/token"
        }

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(credentials)
        sheet = client.open("Eventi in Friuli").worksheet("Itinerarinellarte")

        logging.info("Google Sheets connesso")
    except Exception as e:
        logging.error(f"Errore Google Sheets: {e}")
        return

    # ---- pulizia foglio ----
    sheet.batch_clear(["A2:F10000"])

    # ---- scraping ----
    eventi_totali = []

    for page in range(MAX_PAGES + 1):
        url = URL_EVENTI if page == 0 else f"{URL_EVENTI}?page={page}"
        logging.info(f"Scraping pagina {page}")

        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            logging.error(e)
            break

        soup = BeautifulSoup(r.text, "html.parser")
        eventi = estrai_eventi(soup)
        if not eventi:
            break

        eventi_totali.extend(eventi)
        time.sleep(SLEEP_TIME)

    # ---- upload ----
    if not eventi_totali:
        logging.info("Nessun evento trovato")
        return

    eventi_totali.sort(key=lambda e: e["data_sort"])
    righe = [
        [e["titolo"], e["data"], e["ora"], e["luogo"], e["link"], e["categoria"]]
        for e in eventi_totali
    ]

    sheet.append_rows(righe)
    logging.info(f"{len(righe)} eventi caricati")


if __name__ == "__main__":
    main()
