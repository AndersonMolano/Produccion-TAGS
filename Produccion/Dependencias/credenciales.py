import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLIENT_SECRET_FILE = os.path.join(
    BASE_DIR,
    "client_secret.json"
)

TOKEN_FILE = os.path.join(
    BASE_DIR,
    "token.pickle"
)


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]



def obtener_credenciales():

    creds = None

    if os.path.exists(TOKEN_FILE):

        with open(TOKEN_FILE, "rb") as token:

            creds = pickle.load(token)

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

        else:

            flow = InstalledAppFlow.from_client_secrets_file(

                CLIENT_SECRET_FILE,

                SCOPES

            )

            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:

            pickle.dump(creds, token)

    return creds

if __name__ == "__main__":

    obtener_credenciales()

    print("✅ Credenciales generadas.")





