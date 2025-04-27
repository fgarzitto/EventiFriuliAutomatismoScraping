import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta

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

        # Lettura di tutti i dati dai fogli (escluso il primo)
        all_data = []
        for sheet in all_sheets[1:]:
            records = sheet.get_all_records()
            all_data.extend(records)

        # Conversione in DataFrame
        df = pd.DataFrame(all_data)

        # Gestione della colonna 'data'
        if 'data' in df.columns:
            # Prima controlliamo se sono numeri (seriali di Excel/Sheets)
            def converti_data(x):
                if isinstance(x, (int, float)):  # Se è un numero
                    return datetime(1899, 12, 30) + timedelta(days=x)
                try:
                    return datetime.strptime(x, '%d %b %Y')
                except:
                    return pd.NaT

            df['data'] = df['data'].apply(converti_data)

            # Ordina per data
            df = df.sort_values(by='data')

            # Dopo l'ordinamento rimetti la data come testo
            df['data'] = df['data'].dt.strftime('%d %b %Y')

        # Scrittura nel primo tab
        first_sheet = all_sheets[0]
        first_sheet.clear()
        first_sheet.update([df.columns.values.tolist()] + df.fillna('').values.tolist())

        print("Dati copiati e ordinati con successo nel primo tab!")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    unisci_e_ordina_eventi()
