from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import io
import base64
import fitz  # PyMuPDF
import segno
from io import BytesIO
import logging


app = FastAPI()


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