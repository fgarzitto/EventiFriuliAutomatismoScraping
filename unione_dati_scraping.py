import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

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

            # Funzione per convertire le date in oggetti datetime
            def converti_data(x):
                try:
                    # Se la data è nel formato "30 Apr 2025"
                    return datetime.strptime(x.strip(), "%d %b %Y")
                except ValueError:
                    print(f"⚠️ Data non valida: {x}")  # Avviso per valori errati
                    return pd.NaT  # Se fallisce, mettiamo "Not a Time"

            # Applica la conversione alla colonna 'Data'
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

            # Eliminiamo la colonna temporanea usata per il parsing
            df = df.drop(columns=['Data_parsed'])

        else:
            print("⚠️ Colonna 'Data' non trovata. I dati non saranno ordinati per data.")

        # Scrittura nel primo foglio
        first_sheet = all_sheets[0]
        first_sheet.clear()  # Cancella i dati esistenti nel foglio
        first_sheet.update([df.columns.values.tolist()] + df.fillna('').values.tolist())  # Scrive intestazione + dati

        print("✅ Dati copiati e ordinati con successo nel primo tab!")

    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    unisci_e_ordina_eventi()