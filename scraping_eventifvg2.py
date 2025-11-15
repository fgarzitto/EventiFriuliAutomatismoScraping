import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import logging

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mappa manuale dei nomi dei mesi in italiano
mesi_italiani = {
    "Jan": "Gen", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "Mag", "Jun": "Giu",
    "Jul": "Lug", "Aug": "Ago", "Sep": "Set", "Oct": "Ott", "Nov": "Nov", "Dec": "Dic"
}

# URL di partenza
url = 'https://www.eventifvg.it/'

def estrai_eventi(soup):
    eventi = []

    # Trova tutti gli eventi nella pagina
    for evento in soup.find_all('div', class_='tribe-events-calendar-list__event-row'):
        # Estrazione del titolo
        titolo_elem = evento.find('h3', class_='tribe-events-calendar-list__event-title')
        if titolo_elem:
            link_elem = titolo_elem.find('a', class_='tribe-events-calendar-list__event-title-link')
            titolo = link_elem.text.strip() if link_elem else 'Titolo non disponibile'
            link = link_elem['href'] if link_elem and link_elem.has_attr('href') else 'Link non disponibile'
        else:
            titolo = 'Titolo non disponibile'
            link = 'Link non disponibile'

        # Estrazione della data come oggetto datetime
        data_elem = evento.find('time', class_='tribe-events-calendar-list__event-date-tag-datetime')
        if data_elem and data_elem.has_attr('datetime'):
            data_raw = data_elem['datetime']
            try:
                # Converti la data in oggetto datetime
                data = datetime.strptime(data_raw, '%Y-%m-%d')
            except ValueError:
                data = None
        else:
            # Fallback: prova a estrarre la data dai figli del tag <time>
            try:
                data_text = ''.join(data_elem.stripped_strings) if data_elem else ''
                # Converti la data dal formato inglese
                data = datetime.strptime(data_text, '%d %b %Y')
                # Traduci il mese in italiano usando la mappa
                mese_italiano = mesi_italiani[data.strftime('%b')]
                data = data.strftime(f"%d {mese_italiano} %Y")
            except (ValueError, AttributeError):
                data = None  # Se non riesci a ottenere una data, impostala su None

        # Estrazione dell'orario di inizio
        orario_elem = evento.find('time', class_='tribe-events-calendar-list__event-datetime')
        if orario_elem:
            orario_start_elem = orario_elem.find('span', class_='tribe-event-date-start')
            orario = orario_start_elem.text.split('@')[-1].strip() if orario_start_elem else 'Orario non disponibile'
        else:
            orario = 'Orario non disponibile'

        # Estrazione del luogo
        luogo_elem = evento.find('address', class_='tribe-events-calendar-list__event-venue')
        if luogo_elem:
            luogo_title_elem = luogo_elem.find('span', class_='tribe-events-calendar-list__event-venue-title')
            luogo = luogo_title_elem.text.strip() if luogo_title_elem else 'Luogo non disponibile'
        else:
            luogo = 'Luogo non disponibile'

        # Imposta la categoria predefinita se non specificata
        categoria = 'Non specificata'

        # Estrazione della descrizione
        descrizione = evento.find('div', class_='tribe-events-calendar-list__event-description')
        descrizione_text = descrizione.text.strip() if descrizione else 'Descrizione non disponibile'

        # Crea il dizionario dell'evento
        evento_data = {
            'titolo': titolo,
            'data': data,  # Oggetto datetime o None
            'orario': orario,
            'luogo': luogo,
            'link': link,
            'categoria': categoria,
            'descrizione': descrizione_text
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
    data_limite = datetime.now() + timedelta(days=7)

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
            # Controlla che la data sia valida e confronta con la data limite
            if evento['data'] and isinstance(evento['data'], datetime) and evento['data'] > data_limite:
                logging.info(f"Data limite raggiunta: {evento['data']}")
                url_da_scrapare = None
                break

            eventi_totali.append(evento)

        if url_da_scrapare:
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
                f"{e['data'].day:02d} {mesi_italiani[e['data'].strftime('%b')]} {e['data'].year}" if e['data'] else "Data non disponibile",
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
