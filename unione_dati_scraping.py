import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# Mappa dei mesi completi e abbreviati in italiano
mesi_italiani = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04", "maggio": "05", "giugno": "06",
    "luglio": "07", "agosto": "08", "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
    "gen": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "mag": "May", "giu": "Jun",
    "lug": "Jul", "ago": "Ago", "set": "Sep", "ott": "Oct", "nov": "Nov", "dic": "Dec"
}

# Mappa per tradurre i mesi abbreviati inglesi in italiano
mesi_abbreviati_ita = {
    "Jan": "Gen", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "Mag", "Jun": "Giu",
    "Jul": "Lug", "Aug": "Ago", "Sep": "Set", "Oct": "Ott", "Nov": "Nov", "Dec": "Dic"
}

def traduci_mese_in_italiano(data_str):
    """Sostituisce i mesi inglesi abbreviati con quelli in italiano."""
    for mese_eng, mese_ita in mesi_abbreviati_ita.items():
        data_str = data_str.replace(mese_eng, mese_ita)
    return data_str

def traduci_data(data_str):
    """Sostituisce i mesi italiani (completi o abbreviati) con quelli in formato numerico o inglese."""
    for mese, sostituto in mesi_italiani.items():
        data_str = data_str.lower().replace(mese, sostituto)
    return data_str

def converti_data(data_str):
    """Converte una data stringa nel formato richiesto."""
    try:
        # Traduce il mese italiano
        data_str = traduci_data(data_str)
        # Prova a convertire nel formato numerico "dd mm yyyy"
        try:
            return datetime.strptime(data_str.strip(), "%d %m %Y")
        except ValueError:
            # Se fallisce, prova con il formato "dd Mmm yyyy" (abbreviazioni inglesi)
            return datetime.strptime(data_str.strip(), "%d %b %Y")
    except ValueError:
        print(f"⚠️ Data non valida: {data_str}")
        return pd.NaT

def unisci_e_ordina_eventi():
    try:
        # Autenticazione tramite variabili d'ambiente
        client_email = os.getenv("GSHEET_CLIENT_EMAIL")
        private_key = os.getenv("GSHEET_PRIVATE_KEY")
        
        if not client_email or not private_key:
            raise ValueError("Variabili d'ambiente GSHEET_CLIENT_EMAIL o GSHEET_PRIVATE_KEY mancanti.")
        
        credentials_info = {
            "type": "service_account",
            "project_id": "EventiFriuli",
            "private_key_id": "2ad6e92ed5bd78ebb61505057bc75ecb4130b6a6",
            "private_key": private_key.replace('\\n', '\n'),  # Gestisce correttamente le newline
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

        # Apertura del Google Sheet
        spreadsheet = client.open("Eventi in Friuli")
        all_sheets = spreadsheet.worksheets()

        # Controllo se ci sono fogli disponibili
        if not all_sheets:
            raise ValueError("Nessun foglio disponibile nel Google Sheet.")

        # Lettura dei dati dai fogli, ignorando la formattazione
        all_data = []
        for sheet in all_sheets[1:]:  # Salta il primo foglio, che sarà la destinazione
            records = sheet.get_all_records()  # Otteniamo solo i dati. La prima riga viene trattata come intestazione
            all_data.extend(records)

        if not all_data:
            raise ValueError("Nessun dato trovato nei fogli di lavoro.")

        # Conversione in DataFrame
        df = pd.DataFrame(all_data)

        # Debug: stampa delle prime righe per verificare i dati
        print("Prime righe del DataFrame caricato:")
        print(df.head())

        # Controlla se la colonna "Data" esiste nel DataFrame
        if 'Data' in df.columns:
            # Forziamo la colonna 'Data' a essere stringa
            df['Data'] = df['Data'].astype(str)

            # Applica la conversione delle date
            df['Data_parsed'] = df['Data'].apply(converti_data)

            # Debug: stampa dei risultati della conversione
            print("Valori di 'Data_parsed' dopo la conversione:")
            print(df[['Data', 'Data_parsed']].head())

            # Rimuoviamo righe con date non valide
            df = df.dropna(subset=['Data_parsed'])

            # Ordiniamo il DataFrame per data
            df = df.sort_values(by='Data_parsed')

            # Riformattiamo la colonna 'Data' in formato desiderato
            df['Data'] = df['Data_parsed'].dt.strftime('%d %b %Y')

            # Traduci i mesi inglesi abbreviati in italiano
            df['Data'] = df['Data'].apply(traduci_mese_in_italiano)

            # Eliminiamo la colonna temporanea usata per il parsing
            df = df.drop(columns=['Data_parsed'])

        else:
            print("⚠️ Colonna 'Data' non trovata. I dati non saranno ordinati per data.")

        # Scrittura nel primo foglio
        first_sheet = all_sheets[0]
        first_sheet.clear()  # Cancella i dati esistenti nel foglio
        first_sheet.update([df.columns.values.tolist()] + df.fillna('').values.tolist())  # Scrive intestazione + dati

        print("✅ Dati copiati e ordinati con successo nel primo tab!")

        # Rimuoviamo righe duplicate con lo stesso titolo e la stessa data
        # Considera solo le colonne "Titolo" e "Data"
        if 'Titolo' in df.columns and 'Data' in df.columns:
            # Standardizza i dati per evitare problemi con maiuscole/minuscole o spazi
            df['Titolo'] = df['Titolo'].str.strip().str.lower()
            df['Data'] = df['Data'].str.strip()
        
            # Identifica duplicati in base a "Titolo" e "Data"
            duplicati = df[df.duplicated(subset=['Titolo', 'Data'], keep=False)]
            if not duplicati.empty:
                print("⚠️ Righe duplicate trovate e rimosse:")
                print(duplicati)
        
            # Rimuove duplicati mantenendo solo la prima occorrenza
            df = df.drop_duplicates(subset=['Titolo', 'Data'], keep='first')
            print("✅ Eventi duplicati rimossi con successo.")
        else:
            print("⚠️ Colonne 'Titolo' o 'Data' mancanti. Non è stato possibile rimuovere i duplicati.")
        
            except Exception as e:
                print(f"Errore durante l'esecuzione: {e}")

if __name__ == "__main__":
    unisci_e_ordina_eventi()
