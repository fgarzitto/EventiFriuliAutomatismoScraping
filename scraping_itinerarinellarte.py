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

# URL di partenza
url = 'https://www.itinerarinellarte.it/it/mostre/friuli-venezia-giulia'

def estrai_eventi(soup):
    eventi = []
    oggi = datetime.now()
    limite = oggi + timedelta(days=7)

    # Trova tutti gli eventi nella pagina
    for evento in soup.find_all('div', class_='col-date col-lg-6 col-sm-12 texts'):
        titolo_elem = evento.find('h4')
        titolo = titolo_elem.text.strip() if titolo_elem else 'Titolo non disponibile'

        link = 'Link non disponibile'
        link_elem = evento.find('a', class_='pic', href=True)
        if link_elem:
            link = link_elem.get('href', 'Link non disponibile')
            if link.startswith('/'):
                link = f"https://www.itinerarinellarte.it{link}"
        else:
            titolo_link_elem = evento.find('a', title=True, href=True)
            if titolo_link_elem:
                link = titolo_link_elem.get('href', 'Link non disponibile')
                if link.startswith('/'):
                    link = f"https://www.itinerarinellarte.it{link}"

        descrizione_elem = evento.find('p', class_='abstract')
        descrizione = descrizione_elem.text.strip() if descrizione_elem else 'Descrizione non disponibile'

        date_elems = evento.find_all('span', class_='eventi-data')
        if date_elems and len(date_elems) >= 2:
            data_inizio = date_elems[0].text.strip()
            data_fine = date_elems[1].text.strip().replace('-', '').strip()
            try:
                data_inizio = datetime.strptime(data_inizio, "%d/%m/%Y")
                data_fine = datetime.strptime(data_fine, "%d/%m/%Y")
                data_inizio = max(data_inizio, oggi)
                data_fine = min(data_fine, limite)

                for i in range((data_fine - data_inizio).days + 1):
                    data_corrente = data_inizio + timedelta(days=i)
                    evento_data = {
                        'titolo': titolo,
                        'descrizione': descrizione,
                        'data': data_corrente.strftime("%d %b %Y"),
                        'luogo': 'Luogo non disponibile',
                        'link': link,
                        'categoria': 'Mostre',
                    }
                    eventi.append(evento_data)
            except ValueError:
                logging.warning(f"Formato data non valido: {data_inizio} - {data_fine}")
        else:
            logging.warning("Periodo non disponibile per l'evento.")
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

        # Apertura del foglio "Eventi in Friuli" e selezione del foglio "Itinerarinellarte"
        sheet = client.open("Eventi in Friuli").worksheet("Itinerarinellarte")
        logging.info("Foglio aperto con successo: %s", sheet.title)
    except Exception as e:
        logging.error(f"Errore nell'accesso a Google Sheets: {e}")
        return

    try:
        num_rows = len(sheet.get_all_values())
        if num_rows > 1:
            sheet.delete_rows(2, num_rows)
            logging.info("Righe cancellate con successo.")
    except Exception as e:
        logging.error(f"Errore nella cancellazione delle righe: {e}")
        return

    eventi_totali = []
    page = 0
    max_pages = 4

    while page <= max_pages:
        logging.info(f"Scraping pagina {page}...")
        url_da_scrapare = f'{url}' if page == 0 else f'{url}?page={page}'

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url_da_scrapare, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Errore nella richiesta della pagina {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        eventi_pagina = estrai_eventi(soup)
        if not eventi_pagina:
            break

        eventi_totali.extend(eventi_pagina)
        page += 1
        time.sleep(2)

    if eventi_totali:
        eventi_totali.sort(key=lambda e: datetime.strptime(e['data'], "%d %b %Y"))
        eventi_to_append = [[e['titolo'], e['data'], 'Non disponibile', e['luogo'], e['link'], e['categoria']] for e in eventi_totali]
        try:
            sheet.append_rows(eventi_to_append)
            logging.info("Dati caricati su Google Sheets")
        except Exception as e:
            logging.error(f"Errore nel caricamento su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare su Google Sheets.")

if __name__ == "__main__":
    main()