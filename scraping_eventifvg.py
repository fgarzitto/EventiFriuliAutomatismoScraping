import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import dateparser
import logging

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory corrente basata sulla posizione del file
current_dir = os.path.dirname(os.path.abspath(__file__))
logging.info(f"Directory di lavoro corrente: {current_dir}")

# Controlla se il file delle credenziali esiste
credentials_path = os.path.join(current_dir, 'google-creds.json')
if not os.path.exists(credentials_path):
    raise FileNotFoundError(f"Il file '{credentials_path}' non è stato trovato nella directory corrente: {current_dir}")

# Verifica che il file delle credenziali sia un JSON valido
try:
    with open(credentials_path, 'r') as file:
        json.load(file)
    logging.info(f"Il file delle credenziali '{credentials_path}' è valido.")
except json.JSONDecodeError:
    raise ValueError(f"Il file '{credentials_path}' non contiene un JSON valido.")

# URL di partenza
url = 'https://www.eventifvg.it/'

def estrai_eventi(soup):
    eventi = []

    # Trova tutti gli eventi nella pagina
    for evento in soup.find_all('div', class_='tribe-common-g-row tribe-events-calendar-list__event-row'):
        # Estrazione del titolo
        titolo_elem = evento.find('h3', class_='tribe-events-calendar-list__event-title')
        if titolo_elem:
            link_elem = titolo_elem.find('a', class_='tribe-events-calendar-list__event-title-link')
            titolo = link_elem.text.strip() if link_elem else 'Titolo non disponibile'
            link = link_elem['href'] if link_elem and link_elem.has_attr('href') else 'Link non disponibile'
        else:
            titolo = 'Titolo non disponibile'
            link = 'Link non disponibile'

        # Estrazione della data
        data_elem = evento.find('time', class_='tribe-events-calendar-list__event-date-tag-datetime')
        if data_elem and data_elem.has_attr('datetime'):
            # Converte la data nel formato "20 Apr 2025"
            data_raw = data_elem['datetime']
            try:
                data = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d %b %Y')
            except ValueError:
                data = 'Data non disponibile'
        else:
            data = 'Data non disponibile'

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

        # Crea il dizionario dell'evento
        evento_data = {
            'titolo': titolo,
            'data': data,
            'orario': orario,
            'luogo': luogo,
            'link': link,
            'categoria': categoria,
        }

        logging.info(f"Evento trovato: {evento_data}")
        eventi.append(evento_data)

    return eventi

def data_to_datetime(data_str):
    # Data passata come stringa per la conversione
    return dateparser.parse(data_str, settings={'PREFER_DATES_FROM': 'future'})

def main():
    try:
        # Autenticazione con Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        client = gspread.authorize(creds)

        # Apertura del foglio "Eventi in Friuli" e selezione del foglio "EventiFvg"
        sheet = client.open("Eventi in Friuli").worksheet("EventiFvg")
        logging.info("Foglio aperto con successo: %s", sheet.title)
    except Exception as e:
        logging.error(f"Errore nell'accesso a Google Sheets: {e}")
        return

    try:
        # Verifica quante righe ci sono nel foglio
        num_rows = len(sheet.get_all_values())

        # Se ci sono più di una riga (ad esempio, l'intestazione), cancelliamo le righe esistenti
        if num_rows > 1:
            sheet.delete_rows(2, num_rows)
            logging.info("Righe cancellate con successo.")
        else:
            logging.info("Nessuna riga da cancellare.")
    except Exception as e:
        logging.error(f"Errore nella cancellazione delle righe: {e}")
        return

    eventi_totali = []
    url_da_scrapare = url  # URL iniziale (prima pagina)

    # Calcola la data limite (7 giorni dalla data corrente)
    data_corrente = datetime.now()
    data_limite = data_corrente + timedelta(days=7)

    while url_da_scrapare:
        logging.info(f"Scraping URL: {url_da_scrapare}")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
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
            try:
                data_evento = datetime.strptime(evento['data'], '%d %b %Y')
                if data_evento > data_limite:
                    logging.info(f"Raggiunta la data limite: {data_evento}. Interrompiamo lo scraping.")
                    url_da_scrapare = None
                    break
            except ValueError:
                logging.warning(f"Impossibile analizzare la data dell'evento: {evento['data']}")
                continue

            eventi_totali.append(evento)

        if url_da_scrapare:
            next_page_elem = soup.find('a', class_='tribe-events-c-nav__next')
            if next_page_elem and next_page_elem.has_attr('href'):
                url_da_scrapare = next_page_elem['href']
            else:
                logging.info("Nessuna pagina successiva trovata, fermiamo lo scraping.")
                break

        time.sleep(2)

    if eventi_totali:
        eventi_to_append = [[e['titolo'], e['data'], e['orario'], e['luogo'], e['link'], e['categoria']] for e in eventi_totali]
        logging.info(f"Dati da caricare su Google Sheets: {eventi_to_append}")
        try:
            sheet.append_rows(eventi_to_append)
            logging.info("Dati caricati su Google Sheets")
        except Exception as e:
            logging.error(f"Errore nel caricamento su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare su Google Sheets.")

if __name__ == "__main__":
    main()