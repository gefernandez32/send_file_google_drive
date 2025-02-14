import os
import base64
from fastapi import FastAPI, HTTPException
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = FastAPI()

# Define el alcance de la API de Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_gdrive_service():
    creds = None
    # Carga las credenciales desde token.pickle si existen
    if os.path.exists("token.pickle"):
        creds = Credentials.from_authorized_user_file("token.pickle", SCOPES)
    # Si no hay credenciales válidas, inicia el flujo de autenticación
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open("token.pickle", "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


@app.get("/download-file/")
async def download_file(folder_name: str, file_name: str):
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
            raise HTTPException(status_code=404, detail="Folder not found")

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
            raise HTTPException(status_code=404, detail="File not found")

        file_id = files[0]["id"]

        # Descargar el archivo
        request = service.files().get_media(fileId=file_id)
        file_data = request.execute()

        # Convertir el archivo a Base64
        file_base64 = base64.b64encode(file_data).decode("utf-8")

        return {"file_name": file_name, "content_base64": file_base64}

    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"An error occurred: {error}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
