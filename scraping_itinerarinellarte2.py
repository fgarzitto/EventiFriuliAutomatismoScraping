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

    # Mappa dei mesi in italiano
    mesi = {
        1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
        7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
    }

    # Trova tutti gli eventi
    for evento in soup.find_all('a', class_='row-tile'):
        # Estrazione del titolo
        titolo_elem = evento.find('h3')
        titolo = 'Titolo non disponibile'
        if titolo_elem:
            titolo = titolo_elem.text.strip()

        # Estrazione del link
        link = evento['href'] if evento.has_attr('href') else 'Link non disponibile'
        if link.startswith('/'):  # Se il link è relativo, creiamo il link assoluto
            link = f"https://www.itinerarinellarte.it{link}"

        # Estrazione della data di inizio e fine
        date_elems = evento.find_all('span', class_='eventi-data')
        data_inizio = 'Data non disponibile'
        data_fine = 'Data non disponibile'
        if len(date_elems) >= 2:
            data_inizio = date_elems[0].text.strip()
            data_fine = date_elems[1].text.strip().replace('-', '').strip()
            try:
                data_inizio = datetime.strptime(data_inizio, "%d/%m/%Y")
                data_fine = datetime.strptime(data_fine, "%d/%m/%Y")
                data_inizio = max(data_inizio, oggi)
                data_fine = min(data_fine, limite)

                for i in range((data_fine - data_inizio).days + 1):
                    data_corrente = data_inizio + timedelta(days=i)
                    data_formattata = f"{data_corrente.day:02d} {mesi[data_corrente.month]} {data_corrente.year}"
                    evento_data = {
                        'titolo': titolo,
                        'data': data_formattata,
                        'data_sort': data_corrente,  # <-- Aggiunto campo per ordinare
                        'ora': 'Ora non disponibile',
                        'luogo': 'Luogo non disponibile',
                        'link': link,
                        'categoria': 'Mostre',
                    }
                    eventi.append(evento_data)
            except ValueError:
                logging.warning(f"Formato data non valido: {data_inizio} - {data_fine}")
        else:
            logging.warning("Periodo non disponibile per l'evento.")

        # Estrazione del luogo dal nuovo codice
        luogo = 'Luogo non disponibile'
        luogo_elem = evento.find('header', itemprop='location')
        if luogo_elem:
            luogo_meta = luogo_elem.find('meta', itemprop='name')
            if luogo_meta and 'content' in luogo_meta.attrs:
                luogo_completo = luogo_meta['content'].strip()
                # Estrazione del luogo abbreviato "Passariano di Codroipo (UD)"
                # Supponiamo che il nome del luogo inizia da "Passariano di Codroipo"
                luogo = luogo_completo.split(',')[0].strip()
                # Aggiungiamo il codice della provincia (es. Udine)
                if '(' in luogo_completo and ')' in luogo_completo:
                    luogo = luogo_completo.split('(')[0].strip() + " (" + luogo_completo.split('(')[1].split(')')[0] + ")"

            logging.info(f"Luogo estratto: {luogo}")
        
    return eventi


def main():
    try:
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
        eventi_totali.sort(key=lambda e: e['data_sort'])  # <-- Ordinamento corretto
        eventi_to_append = [[e['titolo'], e['data'], e['ora'], e['luogo'], e['link'], e['categoria']] for e in eventi_totali]
        try:
            sheet.append_rows(eventi_to_append)
            logging.info("Dati caricati su Google Sheets")
        except Exception as e:
            logging.error(f"Errore nel caricamento su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare su Google Sheets.")

if __name__ == "__main__":
    main()
