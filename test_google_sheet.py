import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def test_google_sheet_access():
    # Legge i segreti dall'ambiente
    client_email = os.getenv("GSHEET_CLIENT_EMAIL")
    private_key = os.getenv("GSHEET_PRIVATE_KEY")  # Nessuna sostituzione necessaria

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

    # Autenticazione
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
    client = gspread.authorize(credentials)

    # Verifica l'accesso al Google Sheet
    try:
        sheet_id = "1XuiL6v5EJAJDae5JwZBrA2Uu2zJ4YlUIYPCoK_0W6AI"  # Sostituisci con l'ID del Google Sheet
        sheet = client.open_by_key(sheet_id)
        print(f"Accesso riuscito al Google Sheet: {sheet.title}")
    except Exception as e:
        print(f"Errore nell'accesso al Google Sheet: {e}")
        exit(1)

if __name__ == "__main__":
    test_google_sheet_access()