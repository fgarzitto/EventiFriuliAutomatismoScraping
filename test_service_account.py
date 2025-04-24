import gspread
from oauth2client.service_account import ServiceAccountCredentials

def test_google_sheets_access():
    # Percorso alle credenziali del Service Account
    credentials_path = "google-creds.json"  # Assicurati che il file sia nella root del repo

    # Scope per Google Sheets e Google Drive API
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    
    try:
        # Autenticazione del client
        client = gspread.authorize(creds)
        
        # Sostituisci "Nome del Google Sheet" con il nome esatto del tuo foglio Google Sheets
        sheet = client.open("Eventi in Friuli").sheet1  # Accesso alla prima scheda del foglio
        
        # Esegui una semplice lettura
        data = sheet.get_all_records()  # Ottieni tutti i dati come lista di dizionari
        print("Accesso riuscito! Ecco i dati presenti nel foglio:")
        print(data)
    except Exception as e:
        print("Errore durante l'accesso al foglio:")
        print(e)

if __name__ == "__main__":
    test_google_sheets_access()