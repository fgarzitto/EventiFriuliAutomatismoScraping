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

# Funzioni di parsing

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

def estrai_luogo(evento, is_big):
    if is_big:
        luogo_elem = evento.find('div', class_='info_rows info_location')
        return luogo_elem.find('strong', class_='col2').text.strip() if luogo_elem else 'Luogo non disponibile'
    else:
        col2 = evento.find('div', class_='col2')
        return col2.find('strong').text.strip() if col2 and col2.find('strong') else 'Luogo non disponibile'

def estrai_categoria(evento, is_big):
    if is_big:
        cat = evento.find('div', class_='info_rows info_category')
        return cat.find('strong', class_='col2').text.strip() if cat else 'Categoria non disponibile'
    else:
        col3 = evento.find('div', class_='col3')
        return col3.get("title", "Categoria non disponibile") if col3 else 'Categoria non disponibile'

def crea_evento(evento, titolo, data, is_big):
    try:
        data_parsed = dateparser.parse(data, settings={'DATE_ORDER': 'DMY'}, languages=['it'])
        if data_parsed:
            data = data_parsed.strftime('%d %b %Y')
    except Exception as e:
        logging.warning(f"Errore parsing data evento: {data}, {e}")

    luogo = estrai_luogo(evento, is_big)
    ora = evento.find('div', class_='c-bigEvent__time')
    ora_txt = ora.text.strip() if ora and is_big else 'Ora non disponibile'
    categoria = estrai_categoria(evento, is_big)
    link = 'https://www.turismofvg.it' + evento['href'] if evento.get('href') else 'Link non disponibile'

    return {
        'titolo': titolo.strip(),
        'data': data,
        'luogo': luogo,
        'ora': ora_txt,
        'link': link,
        'categoria': categoria,
        'tipo': 'big' if is_big else 'small'
    }

def parse_data_sicura(data_str):
    parsed = dateparser.parse(data_str, settings={'DATE_ORDER': 'DMY'}, languages=['it'])
    if not parsed:
        logging.warning(f"Data non parsata correttamente: {data_str}")
    return parsed or datetime.max

def estrai_eventi(soup):
    eventi = []
    oggi = datetime.now()
    limite = oggi + timedelta(days=7)

    for e in soup.find_all('a', class_='c-eventsResults__item'):
        is_big = e.find('h1', class_='title') is not None
        has_periodo = e.find('span', class_='multiple_days_string') is not None

        titolo = e.find('h1', class_='title').text if is_big else e.find('h2', class_='title').text
        titolo = titolo.strip()

        if has_periodo:
            periodo = estrai_dati_evento_periodo(e)
            if periodo != 'Data non disponibile':
                try:
                    inizio_str, fine_str = periodo.split(" - ")
                    inizio = datetime.strptime(inizio_str, '%d %b %Y')
                    fine = datetime.strptime(fine_str, '%d %b %Y')
                    inizio = max(inizio, oggi)
                    fine = min(fine, limite)
                    for i in range((fine - inizio).days + 1):
                        d = inizio + timedelta(days=i)
                        eventi.append(crea_evento(e, titolo, d.strftime('%d %b %Y'), is_big))
                except Exception as e:
                    logging.warning(f"Errore gestione periodo: {e}")
        else:
            data = estrai_dati_evento_grande(e) if is_big else estrai_dati_evento_piccolo(e)
            eventi.append(crea_evento(e, titolo, data, is_big))

    eventi.sort(key=lambda e: parse_data_sicura(e['data']))
    return eventi

def main():
    # Autenticazione con Google Sheets utilizzando variabili d'ambiente
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