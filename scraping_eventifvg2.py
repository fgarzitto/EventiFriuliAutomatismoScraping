import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging
import re  # Per il parsing migliorato delle date

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mappa dei mesi in italiano
mesi_italiani = {
    "Gennaio": "01", "Febbraio": "02", "Marzo": "03", "Aprile": "04", "Maggio": "05", "Giugno": "06",
    "Luglio": "07", "Agosto": "08", "Settembre": "09", "Ottobre": "10", "Novembre": "11", "Dicembre": "12"
}

# URL di partenza
url = 'https://www.eventifvg.it/'

def estrai_eventi(soup):
    eventi = []

    # Trova tutti gli eventi nella pagina
    for evento in soup.find_all('div', class_='tribe-events-calendar-list__event-wrapper'):
        # Estrazione del titolo
        titolo_elem = evento.find('h3', class_='tribe-events-calendar-list__event-title')
        if titolo_elem:
            link_elem = titolo_elem.find('a', class_='tribe-events-calendar-list__event-title-link')
            titolo = link_elem.text.strip() if link_elem else 'Titolo non disponibile'
            link = link_elem['href'] if link_elem and link_elem.has_attr('href') else 'Link non disponibile'
        else:
            titolo = 'Titolo non disponibile'
            link = 'Link non disponibile'

        # Estrazione della data e orario dal tag <span class="tribe-event-date-start">
        data_elem = evento.find('span', class_='tribe-event-date-start')
        if data_elem:
            data_raw = data_elem.text.strip()
            logging.info(f"Data raw trovata: {data_raw}")  # Log per debug

            # Rimuovi eventuali virgole dalla data
            data_raw = re.sub(r',', '', data_raw)

            # Split della data per ottenere il mese, giorno e orario
            try:
                # Esempio: "Novembre 23, 2026 @ 21:00" o "Settembre 4, 2026 @ 9:00"
                mese, giorno_orario = data_raw.split(" ", 1)
                giorno, orario = giorno_orario.split(" @ ", 1)

                # Ottieni il numero del mese dalla mappa
                mese_numero = mesi_italiani.get(mese, None)
                if mese_numero:
                    # Crea la data nel formato desiderato
                    data = datetime.strptime(f"{giorno} {mese_numero} {datetime.now().year} {orario}", "%d %m %Y %H:%M")
                else:
                    data = None
            except Exception as e:
                logging.warning(f"Errore nell'elaborazione della data: {data_raw} - {e}")
                data = None
        else:
            data = None

        # Estrazione dell'orario (separato dall'elemento "orario")
        orario = 'Orario non disponibile'
        if data_elem:
            orario = orario.strip()  # Ho già estratto l'orario in precedenza con la logica di split

        # Estrazione del luogo
        luogo_elem = evento.find('address', class_='tribe-events-calendar-list__event-venue')
        luogo = 'Luogo non disponibile'
        if luogo_elem:
            luogo_title_elem = luogo_elem.find('span', class_='tribe-events-calendar-list__event-venue-title')
            luogo = luogo_title_elem.text.strip() if luogo_title_elem else luogo

        # Estrazione della descrizione
        descrizione_elem = evento.find('div', class_='tribe-events-calendar-list__event-description')
        descrizione = descrizione_elem.text.strip() if descrizione_elem else 'Descrizione non disponibile'

        # Crea il dizionario per l'evento
        evento_data = {
            'titolo': titolo,
            'data': data,  # Oggetto datetime o None
            'orario': orario,
            'luogo': luogo,
            'link': link,
            'categoria': 'Non specificata',  # Aggiungi qui la logica per la categoria se necessario
            'descrizione': descrizione
        }

        logging.info(f"Evento trovato: {evento_data}")
        eventi.append(evento_data)

    return eventi

def main():
    try:
        # Autenticazione con Google Sheets
        client_email = os.getenv("GSHEET_CLIENT_EMAIL")
        private_key = os.getenv("GSHEET_PRIVATE_KEY")

        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",
            "private_key_id": "2ad6e92ed5bd78ebb61505057bc75ecb4130b6a6",
            "private_key": private_key,
            "client_email": client_email,
            "client_id": "103136377669455790448",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(credentials)

        # Apertura del foglio Google Sheets
        sheet = client.open("Eventi in Friuli").worksheet("EventiFvg")
        logging.info("Foglio aperto con successo: %s", sheet.title)
    except Exception as e:
        logging.error(f"Errore nell'accesso a Google Sheets: {e}")
        return

    try:
        # Verifica e cancella righe esistenti
        num_rows = len(sheet.get_all_values())
        if num_rows > 1:
            sheet.delete_rows(2, num_rows)
            logging.info("Righe cancellate con successo.")
    except Exception as e:
        logging.error(f"Errore nella cancellazione delle righe: {e}")
        return

    eventi_totali = []
    url_da_scrapare = url
    data_limite = datetime.now()

    while url_da_scrapare:
        logging.info(f"Scraping URL: {url_da_scrapare}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url_da_scrapare, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Errore nella richiesta dell'URL {url_da_scrapare}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        eventi_pagina = estrai_eventi(soup)

        if not eventi_pagina:
            logging.info("Nessun evento trovato nella pagina.")
            break

        for evento in eventi_pagina:
            eventi_totali.append(evento)

        next_page_elem = soup.find('a', class_='tribe-events-c-nav__next')
        url_da_scrapare = next_page_elem['href'] if next_page_elem and next_page_elem.has_attr('href') else None
        time.sleep(2)

    if eventi_totali:
        # Ordina gli eventi per data
        eventi_totali.sort(key=lambda e: e['data'] if e['data'] else datetime.max)

        # Prepara i dati per la scrittura su Google Sheets
        righe = [
            [
                e['titolo'],
                f"{e['data'].day:02d} {mesi_italiani[e['data'].strftime('%B')]} {e['data'].year}" if e['data'] else "Data non disponibile",
                e['orario'],
                e['luogo'],
                e['link'],
                e['categoria'],
                e['descrizione']
            ]
            for e in eventi_totali
        ]

        try:
            sheet.append_rows(righe)
            logging.info("Dati caricati su Google Sheets.")
        except Exception as e:
            logging.error(f"Errore durante il caricamento su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare.")

if __name__ == "__main__":
    main()
