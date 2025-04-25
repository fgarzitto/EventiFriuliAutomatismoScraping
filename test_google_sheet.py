import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def test_google_sheet_access():
    # Legge i segreti dall'ambiente
    client_email = os.getenv("GSHEET_CLIENT_EMAIL")
    private_key = os.getenv("GSHEET_PRIVATE_KEY")  # Nessuna sostituzione necessaria

    # Configura le credenziali
    credentials_info = {
        "type": "service_account",
        "client_email": client_email,
        "private_key": private_key,
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
    client = gspread.authorize(credentials)

    # Verifica l'accesso al Google Sheet
    try:
        sheet_id = "1XuiL6v5EJAJDae5JwZBrA2Uu2zJ4YlUIYPCoK_0W6AI"  # Sostituisci con l'ID del tuo Google Sheet
        sheet = client.open_by_key(sheet_id)
        print(f"Accesso riuscito al Google Sheet: {sheet.title}")
    except Exception as e:
        print(f"Errore nell'accesso al Google Sheet: {e}")
        exit(1)

if __name__ == "__main__":
    test_google_sheet_access()