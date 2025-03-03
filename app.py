import os
import base64
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import io
import fitz
import segno
from io import BytesIO
import logging

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

app = FastAPI(
    title="Python para Desarrolladores Genexus",
    description="Esta API es la que usaremos en la formación de Python para Desarrolladores Genexus",
    version="1.0.0",
    servers=[
        {"url": "https://send-file-google-drive.onrender.com", "description": "Servidor de producción"},
        {"url": "http://localhost:8000", "description": "Servidor local"},
    ],
)

# Definir el modelo de entrada
class SignPdfRequest(BaseModel):
    pdf_base64: str
    image_base64: str
    x: int = 400
    y: int = 650
    width: int = 200
    height: int = 150


class QRRequestModel(BaseModel):
    website: str

class PedidoRequest(BaseModel):
    nro_pedido: str
    estado: str
    fecha: str
    cliente: str

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


@app.post("/sign-pdf")
async def sign_pdf(request: SignPdfRequest):
    try:
        # Base64 encoded PDF and image strings
        pdf_base64 = request.pdf_base64
        image_base64 = request.image_base64

        # Decode the base64 strings
        pdf_data = base64.b64decode(pdf_base64)
        image_data = base64.b64decode(image_base64)

        # Wrap the decoded data in BytesIO streams
        pdf_stream = io.BytesIO(pdf_data)
        image_stream = io.BytesIO(image_data)

        # Open the PDF from the stream
        pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")

        # Get the first page
        page = pdf_document[0]

        # Specify the position and size of the image
        x, y, width, height = request.x, request.y, request.width, request.height

        # Insert the image on the first page
        page.insert_image(fitz.Rect(x, y, x + width, y + height), stream=image_stream)

        # Save the modified PDF
        output_pdf_path = "recibo_sueldo_con_imagen.pdf"
        pdf_document.save(output_pdf_path)

        with open(output_pdf_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()

        # Encode the PDF data to base64
        pdf_base64 = base64.b64encode(pdf_data).decode("utf-8")

        # Close the PDF
        pdf_document.close()

        return {"pdf_base64": pdf_base64}

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@app.post("/get-qr")
async def get_qr(request: QRRequestModel):
    website = request.website
    qr_code = segno.make_qr(website)
    buffer = BytesIO()
    qr_code.save(buffer, kind="png", scale=4)
    byte_data = buffer.getvalue()
    base64_data = base64.b64encode(byte_data).decode("utf-8")
    print(base64_data)
    return {"qr_base64": base64_data}


@app.get("/keep-alive")
async def keep_alive():
    print("Alive!")

@app.get("/pedidos/{nro_pedido}", response_model=PedidoRequest)
async def obtener_pedido(nro_pedido: str):
    pedidos_db = {
        "100": {"nro_pedido": "100", "estado": "Entregado", "fecha": "2023-10-01", "cliente": "Juan Pérez"},
        "101": {"nro_pedido": "101", "estado": "En proceso", "fecha": "2023-10-02", "cliente": "Ana Gómez"},
}
    # Buscar el pedido en la "base de datos"
    pedido = pedidos_db.get(nro_pedido)
    
    # Si el pedido no existe, devolver un error 404
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    # Retornar los detalles del pedido
    return pedido
    


# Para ejecutar el servidor Uvicorn
# uvicorn app2:app --reload

