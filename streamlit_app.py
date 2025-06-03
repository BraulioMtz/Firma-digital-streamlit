import streamlit as st
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import snowflake.connector

st.title("🔐 Firma Digital de Documentos PDF")

uploaded_file = st.file_uploader("📄 Sube un PDF para firmar", type=["pdf"])

if uploaded_file:
    # 1. Cargar clave privada desde Snowflake
    conn = snowflake.connector.connect(
        user='BRAUMTZ',
        password='SnowflakeNueva-1',
        account='GZWCUFB-ZF58512',
        warehouse='COMPUTE_WH',
        database='RETO_CRIPTO',
        schema='PUBLIC'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT clave_privada FROM claves_privadas WHERE id = 'firma_general'")
    clave_pem = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    # 2. Cargar clave privada y derivar clave pública
    private_key = serialization.load_pem_private_key(
        clave_pem.encode(),
        password=None
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # 3. Leer el PDF
    reader = PdfReader(uploaded_file)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    # 4. Escribir PDF temporal sin página de verificación
    temp_pdf = io.BytesIO()
    writer.write(temp_pdf)
    temp_pdf_bytes = temp_pdf.getvalue()

    # 5. Calcular hash del contenido PDF
    hash_obj = hashes.Hash(hashes.SHA256())
    hash_obj.update(temp_pdf_bytes)
    digest = hash_obj.finalize()

    # 6. Firmar el hash
    signature = private_key.sign(
        digest,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    # 7. Crear página de verificación visible
    extra_page = io.BytesIO()
    c = canvas.Canvas(extra_page, pagesize=letter)
    c.setFont("Helvetica", 10)
    c.drawString(100, 750, "✅ Documento firmado digitalmente")
    c.drawString(100, 730, f"📅 Fecha de firma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(100, 710, "🔐 Clave pública (PEM):")
    for i, line in enumerate(public_pem.splitlines()):
        c.drawString(100, 690 - i*12, line)
    c.drawString(100, 500, "✍️ Firma digital (hex):")
    for i, line in enumerate(signature.hex()[i:i+80] for i in range(0, len(signature.hex()), 80)):
        c.drawString(100, 480 - i*12, line)
    c.save()
    extra_page.seek(0)

    # 8. Agregar la página de verificación
    extra_pdf = PdfReader(extra_page)
    writer.add_page(extra_pdf.pages[0])

    # 9. Descargar el PDF final
    output_final = io.BytesIO()
    writer.write(output_final)
    st.download_button("📥 Descargar PDF Firmado", output_final.getvalue(), file_name="firmado.pdf", mime="application/pdf")
