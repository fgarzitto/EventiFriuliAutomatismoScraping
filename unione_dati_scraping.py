import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# Mappa dei mesi completi e abbreviati in italiano
mesi_italiani = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04", "maggio": "05", "giugno": "06",
    "luglio": "07", "agosto": "08", "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
    "gen": "01", "feb": "02", "mar": "03", "apr": "04", "mag": "05", "giu": "06",
    "lug": "07", "ago": "08", "set": "09", "ott": "10", "nov": "11", "dic": "12"
}

# Mappa per tradurre i mesi inglesi abbreviati in italiano
mesi_abbreviati_ita = {
    "Jan": "Gen", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "Mag", "Jun": "Giu",
    "Jul": "Lug", "Aug": "Ago", "Sep": "Set", "Oct": "Ott", "Nov": "Nov", "Dec": "Dic"
}

# Mappa per tradurre abbreviazioni italiane in inglese
mesi_italiani_abbr = {
    "gen": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "mag": "May", "giu": "Jun",
    "lug": "Jul", "ago": "Aug", "set": "Sep", "ott": "Oct", "nov": "Nov", "dic": "Dec"
}

def traduci_mese_in_italiano(data_str):
    for mese_eng, mese_ita in mesi_abbreviati_ita.items():
        data_str = data_str.replace(mese_eng, mese_ita)
    return data_str

def traduci_data(data_str):
    for mese, sostituto in mesi_italiani.items():
        data_str = data_str.lower().replace(mese, sostituto)
    return data_str

def italiano_to_inglese_abbr(data_str):
    for mese_ita, mese_eng in mesi_italiani_abbr.items():
        data_str = data_str.lower().replace(mese_ita, mese_eng)
    return data_str

def converti_data(data_str):
    try:
        # Prova formato numerico (es. "03 08 2025")
        data_str_numerica = traduci_data(data_str)
        try:
            return datetime.strptime(data_str_numerica.strip(), "%d %m %Y")
        except ValueError:
            pass

        # Prova formato testuale inglese abbreviato (es. "03 Aug 2025")
        data_str_eng = italiano_to_inglese_abbr(data_str)
        return datetime.strptime(data_str_eng.strip().title(), "%d %b %Y")

    except ValueError:
        print(f"⚠️ Data non valida: {data_str}")
        return pd.NaT

def unisci_e_ordina_eventi():
    try:
        client_email = os.getenv("GSHEET_CLIENT_EMAIL")
        private_key = os.getenv("GSHEET_PRIVATE_KEY")
        
        if not client_email or not private_key:
            raise ValueError("Variabili d'ambiente GSHEET_CLIENT_EMAIL o GSHEET_PRIVATE_KEY mancanti.")
        
        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",
            "private_key_id": "2ad6e92ed5bd78ebb61505057bc75ecb4130b6a6",
            "private_key": private_key.replace('\\n', '\n'),
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

        spreadsheet = client.open("Eventi in Friuli")
        all_sheets = spreadsheet.worksheets()

        if not all_sheets:
            raise ValueError("Nessun foglio disponibile nel Google Sheet.")

        all_data = []
        for sheet in all_sheets[1:]:  # Salta il primo foglio
            records = sheet.get_all_records()
            all_data.extend(records)

        if not all_data:
            raise ValueError("Nessun dato trovato nei fogli di lavoro.")

        df = pd.DataFrame(all_data)

        print("Prime righe del DataFrame caricato:")
        print(df.head())

        if 'Data' in df.columns:
            df['Data'] = df['Data'].astype(str)
            df['Data_parsed'] = df['Data'].apply(converti_data)

            non_parse = df[df['Data_parsed'].isna()]
            if not non_parse.empty:
                print("⛔️ Date non parseabili:")
                print(non_parse[['Data']])

            df = df.dropna(subset=['Data_parsed'])
            df = df.sort_values(by='Data_parsed')

            # Ottieni la data odierna, ma solo la parte della data (senza orario)
            oggi = datetime.today().date()

            # Filtra il DataFrame per escludere le date precedenti ad oggi, inclusa la data odierna
            df = df[df['Data_parsed'].dt.date >= oggi]

            # Formatta la colonna Data
            df['Data'] = df['Data_parsed'].dt.strftime('%d %b %Y')
            df['Data'] = df['Data'].apply(traduci_mese_in_italiano)
            df = df.drop(columns=['Data_parsed'])
        else:
            print("⚠️ Colonna 'Data' non trovata. I dati non saranno ordinati per data.")

        if 'Titolo' in df.columns and 'Data' in df.columns:
            df['Titolo_normalizzato'] = df['Titolo'].astype(str).str.strip().str.lower()
            df['Data_normalizzata'] = df['Data'].astype(str).str.strip()

            duplicati = df[df.duplicated(subset=['Titolo_normalizzato', 'Data_normalizzata'], keep=False)]
            if not duplicati.empty:
                print("⚠️ Righe duplicate trovate:")
                print(duplicati[['Titolo', 'Data']])

            df = df.drop_duplicates(subset=['Titolo_normalizzato', 'Data_normalizzata'], keep='first')
            df = df.drop(columns=['Titolo_normalizzato', 'Data_normalizzata'])

            print("✅ Eventi duplicati rimossi con successo.")
        else:
            print("⚠️ Colonne 'Titolo' o 'Data' mancanti. Non è stato possibile rimuovere i duplicati.")

        first_sheet = all_sheets[0]
        first_sheet.clear()
        first_sheet.update([df.columns.values.tolist()] + df.fillna('').values.tolist())

        print("✅ Dati copiati e ordinati con successo nel primo tab!")

    except Exception as e:
        print(f"Errore durante l'esecuzione: {e}")

if __name__ == "__main__":
    unisci_e_ordina_eventi()
