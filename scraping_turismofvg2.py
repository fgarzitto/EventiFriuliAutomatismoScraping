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

url = 'https://www.turismofvg.it/eventi'

# Funzioni di parsing per i vari tipi di eventi

def estrai_evento_principale(evento):
    # Estrai il titolo dell'evento principale
    titolo_elem = evento.find('h2', class_='c-events_showreel__title')
    titolo = titolo_elem.text.strip() if titolo_elem else 'Titolo non disponibile'

    # Estrai la data
    data_elem = evento.find('h3')
    data = data_elem.text.strip() if data_elem else 'Data non disponibile'

    # Estrai il luogo
    luogo_elem = evento.find('h4')
    luogo = luogo_elem.text.strip() if luogo_elem else 'Luogo non disponibile'

    # Estrai il link
    link_elem = evento.find('a', class_='c-events_showreel__link')
    link = 'https://www.turismofvg.it' + link_elem['href'] if link_elem else 'Link non disponibile'

    return {
        'titolo': titolo,
        'data': data,
        'luogo': luogo,
        'link': link,
        'categoria': 'Categoria non disponibile',
        'tipo': 'principale'
    }

def estrai_evento_secondo_tipo(evento):
    # Estrai la data
    data_elem = evento.find('div', class_='info_rows info_date')
    if data_elem:
        giorno = data_elem.find('strong').text.strip() if data_elem.find('strong') else 'Giorno non disponibile'
        mese = data_elem.find('p').text.strip() if data_elem.find('p') else 'Mese non disponibile'
        data = f"{giorno} {mese}"  # Data in formato "13 NOV"
    else:
        data = 'Data non disponibile'

    # Estrai il luogo
    luogo_elem = evento.find('div', class_='info_rows info_location')
    luogo = luogo_elem.find('strong', class_='col2').text.strip() if luogo_elem else 'Luogo non disponibile'

    # Estrai la categoria
    categoria_elem = evento.find('div', class_='info_rows info_category')
    categoria = categoria_elem.get('title', 'Categoria non disponibile') if categoria_elem else 'Categoria non disponibile'

    # Estrai il titolo
    titolo_elem = evento.find('h1', class_='title')
    titolo = titolo_elem.text.strip() if titolo_elem else 'Titolo non disponibile'

    return {
        'titolo': titolo,
        'data': data,
        'luogo': luogo,
        'categoria': categoria,
        'link': 'https://www.turismofvg.it' + evento.find('a')['href'] if evento.find('a') else 'Link non disponibile',
        'tipo': 'secondo_tipo'
    }

def estrai_evento_terzo_tipo(evento):
    # Estrai il titolo
    titolo_elem = evento.find('h2', class_='title')
    titolo = titolo_elem.text.strip() if titolo_elem else 'Titolo non disponibile'

    # Estrai la data (giorno e mese)
    data_elem = evento.find('div', class_='info_rows info_date')
    if data_elem:
        giorno = data_elem.find('strong').text.strip() if data_elem.find('strong') else 'Giorno non disponibile'
        mese = data_elem.find('p').text.strip() if data_elem.find('p') else 'Mese non disponibile'
        data = f"{giorno} {mese}"  # Data in formato "13 NOV"
    else:
        data = 'Data non disponibile'

    # Estrai il luogo
    luogo_elem = evento.find('div', class_='info_rows info_location')
    luogo = luogo_elem.find('strong', class_='col2').text.strip() if luogo_elem else 'Luogo non disponibile'

    # Estrai la categoria
    categoria_elem = evento.find('div', class_='info_rows info_category')
    categoria = categoria_elem.get('title', 'Categoria non disponibile') if categoria_elem else 'Categoria non disponibile'

    return {
        'titolo': titolo,
        'data': data,
        'luogo': luogo,
        'categoria': categoria,
        'link': 'https://www.turismofvg.it' + evento.find('a')['href'] if evento.find('a') else 'Link non disponibile',
        'tipo': 'terzo_tipo'
    }

# Funzione per estrarre eventi da tutti i tipi
def estrai_eventi_completi(soup):
    eventi = []

    # Estrai gli eventi principali
    evento_principale = soup.find_all('div', class_='c-events_showreel__info')
    for evento in evento_principale:
        eventi.append(estrai_evento_principale(evento))

    # Estrai il secondo tipo di eventi
    eventi_secondo_tipo = soup.find_all('div', class_='item_info')
    for evento in eventi_secondo_tipo:
        eventi.append(estrai_evento_secondo_tipo(evento))

    # Estrai il terzo tipo di eventi
    for evento in eventi_secondo_tipo:
        eventi.append(estrai_evento_terzo_tipo(evento))

    return eventi

# Funzione principale per eseguire lo scraping e caricare i dati su Google Sheets
def main():
    # Autenticazione con Google Sheets
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
        sheet = client.open("Eventi in Friuli").worksheet("TurismoFvg")
    except Exception as e:
        logging.error(f"Errore accesso Google Sheets: {e}")
        return

    try:
        num_rows = len(sheet.get_all_values())
        if num_rows > 1:
            sheet.delete_rows(2, num_rows)
    except Exception as e:
        logging.error(f"Errore pulizia foglio: {e}")

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
        eventi = estrai_eventi_completi(soup)

        if not eventi:
            break

        eventi_totali.extend(eventi)
        time.sleep(2)

    if eventi_totali:
        righe = [[e['titolo'], e['data'], e['luogo'], e['categoria'], e['link']] for e in eventi_totali]
        try:
            sheet.append_rows(righe)
        except Exception as e:
            logging.error(f"Errore scrittura su Google Sheets: {e}")
    else:
        logging.info("Nessun evento da caricare.")

if __name__ == '__main__':
    main()
