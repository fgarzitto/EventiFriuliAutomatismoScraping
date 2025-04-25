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
url = 'https://www.turismofvg.it/eventi'

# Funzioni di parsing (rimangono inalterate)

def estrai_dati_evento_grande(evento):
    data_elem = evento.find('div', class_='col1')
    if data_elem:
        giorno = data_elem.find('strong')
        mese = data_elem.find('p')
        if giorno and mese:
            data_str = f"{giorno.text.strip()} {mese.text.strip()} {datetime.now().year}"
            data = dateparser.parse(data_str, settings={'DATE_ORDER': 'DMY'}, languages=['it'])
            return data.strftime('%d %b %Y') if data else 'Data non disponibile'
    return 'Data non disponibile'

def estrai_dati_evento_piccolo(evento):
    return estrai_dati_evento_grande(evento)

def estrai_dati_evento_periodo(evento):
    data_elem = evento.find('span', class_='multiple_days_string')
    if data_elem:
        testo = data_elem.text.strip().lower()
        if 'dal' in testo and 'al' in testo:
            try:
                testo = testo.replace('dal', '').strip()
                if ' al ' in testo:
                    inizio, fine = testo.split(' al ')
                    inizio = inizio.strip()
                    fine = fine.strip()
                    if not any(str(y) in inizio for y in range(2020, 2031)):
                        inizio += f" {datetime.now().year}"
                    if not any(str(y) in fine for y in range(2020, 2031)):
                        fine += f" {datetime.now().year}"
                    data_inizio = dateparser.parse(inizio, settings={'DATE_ORDER': 'DMY'}, languages=['it'])
                    data_fine = dateparser.parse(fine, settings={'DATE_ORDER': 'DMY'}, languages=['it'])
                    if data_inizio and data_fine:
                        return f"{data_inizio.strftime('%d %b %Y')} - {data_fine.strftime('%d %b %Y')}"
            except Exception as e:
                logging.error(f"Errore parsing periodo: {e}")
    return 'Data non disponibile'

# Aggiungere altre funzioni di parsing qui...

def main():
    # Configurazione delle credenziali di accesso a Google Sheets
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

        # Apertura del foglio "Eventi in Friuli" e selezione del foglio "TurismoFvg"
        sheet = client.open("Eventi in Friuli").worksheet("TurismoFvg")
        logging.info("Foglio aperto con successo: %s", sheet.title)
    except Exception as e:
        logging.error(f"Errore nell'accesso a Google Sheets: {e}")
        return

    # Proseguire con la logica di scraping e caricamento dei dati...
    eventi_totali = []
    for page in range(20):
        logging.info(f"Scraping pagina {page}...")
        url_page = url if page == 0 else f"{url}?page={page}"

        try:
            r = requests.get(url_page, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
        except Exception as e:
            logging.error(f"Errore richiesta pagina {page}: {e}")
            break

        soup = BeautifulSoup(r.content, 'html.parser')
        eventi = estrai_eventi(soup)
        if not eventi:
            break

        eventi_totali.extend(eventi)
        time.sleep(2)

    if eventi_totali:
        righe = [[e['titolo'], e['data'], e['ora'], e['luogo'], e['link'], e['categoria']] for e in eventi_totali]
        try:
            sheet.append_rows(righe)
        except Exception as e:
            logging.error(f"Errore scrittura su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare.")

if __name__ == '__main__':
    main()