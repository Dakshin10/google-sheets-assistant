import os
import gspread

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GOOGLE_TOKEN_FILE, GOOGLE_CLIENT_SECRET_FILE, GOOGLE_SCOPES


def get_google_client():
    creds = None

    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            str(GOOGLE_TOKEN_FILE),
            GOOGLE_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GOOGLE_CLIENT_SECRET_FILE),
                GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return gspread.authorize(creds)
