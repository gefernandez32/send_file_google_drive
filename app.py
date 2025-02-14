import os
import base64
from fastapi import FastAPI, HTTPException

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib

app = FastAPI()

# Definir los alcances para Google Drive y Gmail
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.send"
]

SENDER_EMAIL = "fernandez.emir@gmail.com"
RECIPIENT_EMAIL = "gabrielfernandez@neuronic.com.ar"


def get_gdrive_service():
    """Autenticación y construcción del servicio de Google Drive."""
    creds = None
    if os.path.exists("token.pickle"):
        creds = Credentials.from_authorized_user_file("token.pickle", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open("token.pickle", "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_gmail_service():
    """Autenticación y construcción del servicio de Gmail."""
    creds = None
    if os.path.exists("token.pickle"):
        creds = Credentials.from_authorized_user_file("token.pickle", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email_with_attachment(file_name: str, file_data: bytes):
    """Envía un email con el archivo descargado de Google Drive como adjunto."""
    try:
        service = get_gmail_service()

        # Crear el mensaje de correo
        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = RECIPIENT_EMAIL
        message["Subject"] = f"Archivo descargado: {file_name}"

        # Adjuntar el archivo
        part = MIMEBase("application", "octet-stream")
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{file_name}"')
        message.attach(part)

        # Convertir el mensaje a base64
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        # Enviar el email
        service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {str(e)}")


@app.get("/download-and-email-file/")
async def download_and_email_file(folder_name: str, file_name: str):
    """Descarga un archivo de Google Drive y lo envía por correo."""
    try:
        service = get_gdrive_service()

        # Buscar la carpeta por nombre
        folder_results = (
            service.files()
            .list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                spaces="drive",
                fields="files(id, name)",
            )
            .execute()
        )
        folders = folder_results.get("files", [])

        if not folders:
            raise HTTPException(status_code=404, detail="Carpeta no encontrada")

        folder_id = folders[0]["id"]

        # Buscar el archivo dentro de la carpeta
        file_results = (
            service.files()
            .list(
                q=f"name='{file_name}' and '{folder_id}' in parents",
                spaces="drive",
                fields="files(id, name)",
            )
            .execute()
        )
        files = file_results.get("files", [])

        if not files:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        file_id = files[0]["id"]

        # Descargar el archivo
        request = service.files().get_media(fileId=file_id)
        file_data = request.execute()

        # Enviar el archivo por correo electrónico
        send_email_with_attachment(file_name, file_data)

        return {"message": "Archivo enviado exitosamente por correo", "file_name": file_name}

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"Ocurrió un error con Google Drive: {error}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

