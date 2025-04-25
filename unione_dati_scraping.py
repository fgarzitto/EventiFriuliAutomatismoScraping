import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import dateparser
import logging

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL di partenza
url = 'https://www.eventifvg.it/'

def estrai_eventi(soup):
    eventi = []
    for evento in soup.find_all('div', class_='tribe-common-g-row tribe-events-calendar-list__event-row'):
        titolo_elem = evento.find('h3', class_='tribe-events-calendar-list__event-title')
        if titolo_elem:
            link_elem = titolo_elem.find('a', class_='tribe-events-calendar-list__event-title-link')
            titolo = link_elem.text.strip() if link_elem else 'Titolo non disponibile'
            link = link_elem['href'] if link_elem and link_elem.has_attr('href') else 'Link non disponibile'
        else:
            titolo = 'Titolo non disponibile'
            link = 'Link non disponibile'

        data_elem = evento.find('time', class_='tribe-events-calendar-list__event-date-tag-datetime')
        if data_elem and data_elem.has_attr('datetime'):
            data_raw = data_elem['datetime']
            data = datetime.strptime(data_raw, '%Y-%m-%d').strftime('%d %b').upper()
        else:
            data = 'Data non disponibile'

        orario_elem = evento.find('time', class_='tribe-events-calendar-list__event-datetime')
        if orario_elem:
            orario_start_elem = orario_elem.find('span', class_='tribe-event-date-start')
            orario = orario_start_elem.text.split('@')[-1].strip() if orario_start_elem else 'Orario non disponibile'
        else:
            orario = 'Orario non disponibile'

        luogo_elem = evento.find('address', class_='tribe-events-calendar-list__event-venue')
        if luogo_elem:
            luogo_title_elem = luogo_elem.find('span', class_='tribe-events-calendar-list__event-venue-title')
            luogo = luogo_title_elem.text.strip() if luogo_title_elem else 'Luogo non disponibile'
        else:
            luogo = 'Luogo non disponibile'

        categoria = ''  # Campo vuoto

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

def main():
    try:
        # Legge i segreti dall'ambiente
        client_email = os.getenv("GSHEET_CLIENT_EMAIL")
        private_key = os.getenv("GSHEET_PRIVATE_KEY")

        # Configura manualmente il dizionario delle credenziali
        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",  # Sostituisci con l'ID del tuo progetto
            "private_key_id": "2ad6e92ed5bd78ebb61505057bc75ecb4130b6a6",  # Sostituisci con l'ID della chiave privata
            "private_key": private_key,
            "client_email": client_email,
            "client_id": "103136377669455790448",  # Sostituisci con l'ID del client
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }

        # Autenticazione con Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        client = gspread.authorize(credentials)

        # Apertura del foglio "Eventi in Friuli" e selezione del foglio "Foglio2"
        sheet = client.open("Eventi in Friuli").worksheet("Foglio2")
        logging.info(f"Foglio aperto con successo: {sheet.title}")
    except Exception as e:
        logging.error(f"Errore nell'accesso a Google Sheets: {e}")
        return

    try:
        num_rows = len(sheet.get_all_values())
        if num_rows > 1:
            sheet.delete_rows(2, num_rows)
            logging.info("Righe cancellate con successo.")
        else:
            logging.info("Nessuna riga da cancellare.")
    except Exception as e:
        logging.error(f"Errore nella cancellazione delle righe: {e}")
        return

    eventi_totali = []
    url_da_scrapare = url

    data_corrente = datetime.now()
    data_limite = data_corrente + timedelta(days=7)

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
            try:
                data_evento = datetime.strptime(evento['data'], '%d %b')
                data_evento = data_evento.replace(year=data_corrente.year)
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