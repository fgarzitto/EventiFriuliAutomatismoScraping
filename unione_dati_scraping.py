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

        # Apertura del Google Sheet
        spreadsheet = client.open("Eventi in Friuli")
        all_sheets = spreadsheet.worksheets()

        # Lettura dei dati dai fogli, ignorando la formattazione
        all_data = []
        for sheet in all_sheets[1:]:
            records = sheet.get_all_records()  # otteniamo solo i dati, non la formattazione
            all_data.extend(records)

        # Conversione in DataFrame
        df = pd.DataFrame(all_data)

        # Debug: stampiamo le prime righe per vedere i dati
        print("Prime righe del DataFrame:")
        print(df.head())

        if 'data' in df.columns:
            # Forziamo la colonna 'data' a essere stringa
            df['data'] = df['data'].astype(str)

            # Funzione per provare a convertire le date
            def converti_data(x):
                try:
                    # Se la data è nel formato "30 Apr 2025"
                    return datetime.strptime(x.strip(), "%d %b %Y")
                except ValueError:
                    print(f"Data non valida: {x}")  # Aggiungiamo un print per vedere i valori errati
                    return pd.NaT  # Se fallisce, mettiamo "Not a Time"

            df['data_parsed'] = df['data'].apply(converti_data)

            # Debug: stampiamo i valori dopo la conversione
            print("Valori di 'data_parsed' dopo la conversione:")
            print(df['data_parsed'].head())

            # Teniamo solo righe valide
            df = df.dropna(subset=['data_parsed'])

            # Ordiniamo per la data vera
            df = df.sort_values(by='data_parsed')

            # Rimettiamo la data nel formato che vuoi
            df['data'] = df['data_parsed'].dt.strftime('%d %b %Y')

            # Eliminiamo la colonna di servizio
            df = df.drop(columns=['data_parsed'])

        # Scrittura nel primo tab
        first_sheet = all_sheets[0]
        first_sheet.clear()
        first_sheet.update([df.columns.values.tolist()] + df.fillna('').values.tolist())

        print("✅ Dati copiati e ordinati con successo nel primo tab!")

    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    unisci_e_ordina_eventi()
