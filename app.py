# app.py (versión modificada)

import os
import io
import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader

# --- Configuración de la Página ---
st.set_page_config(page_title="Chat con Google Drive", page_icon="📄", layout="wide")
st.title("📄 Chat con Documentos de Google Drive")

# --- Configuración de APIs y credenciales ---
# Carga de secretos
try:
    gcp_credentials_dict = st.secrets["gcp_service_account"]
    drive_folder_id = st.secrets["DRIVE_FOLDER_ID"]
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    SECRETS_CONFIGURED = True
except (KeyError, FileNotFoundError):
    st.error("🚨 Error: Faltan secretos en la configuración (Gemini API Key, GCP Service Account o Drive Folder ID).")
    SECRETS_CONFIGURED = False

# --- Funciones para Google Drive ---

# Usamos cache para no reconectar en cada rerun
@st.cache_resource
def connect_to_google_drive():
    """Crea y devuelve un objeto de servicio para interactuar con la API de Drive."""
    try:
        creds = Credentials.from_service_account_info(
            gcp_credentials_dict,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"No se pudo conectar a Google Drive: {e}")
        return None

# Usamos cache para no descargar los archivos en cada interacción del usuario
@st.cache_data(ttl=600) # Cache por 10 minutos
def get_drive_files_content(_service, folder_id):
    """Lee el contenido de los archivos (PDF, TXT) de una carpeta de Drive."""
    if not _service:
        return None, []

    content_list = []
    file_names = []
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = _service.files().list(q=query, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = results.get('files', [])

        for item in items:
            file_id = item['id']
            file_name = item['name']
            mime_type = item['mimeType']

            request = _service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

            file_buffer.seek(0)
            file_names.append(file_name)

            if mime_type == 'application/pdf':
                reader = PdfReader(file_buffer)
                text = "".join(page.extract_text() for page in reader.pages)
                content_list.append(f"--- Contenido de '{file_name}' ---\n{text}\n")
            elif mime_type == 'text/plain':
                text = file_buffer.read().decode('utf-8')
                content_list.append(f"--- Contenido de '{file_name}' ---\n{text}\n")

        return "\n".join(content_list), file_names
    except HttpError as error:
        st.error(f"Ocurrió un error al acceder a los archivos de Drive: {error}")
        return None, []

# --- Funciones de Gemini (Modificadas) ---
def generate_response(query: str, context: str):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Eres un asistente experto en la documentación proporcionada.
    Usando el siguiente contexto extraído de varios documentos, responde la pregunta del usuario.
    Si la respuesta no se encuentra en el contexto, indícalo.

    Contexto:
    {context}

    Pregunta del usuario:
    "{query}"

    Respuesta:
    """
    response = model.generate_content(prompt)
    return response.text

# --- Flujo Principal de la App ---
if SECRETS_CONFIGURED:
    drive_service = connect_to_google_drive()

    with st.spinner("Cargando documentos desde Google Drive..."):
        document_context, file_names = get_drive_files_content(drive_service, drive_folder_id)

    if document_context:
        st.sidebar.header("📄 Archivos en la Base de Conocimiento")
        st.sidebar.info(f"Se cargaron {len(file_names)} archivo(s) desde Google Drive:")
        for name in file_names:
            st.sidebar.markdown(f"- `{name}`")

        # Inicializar historial de chat
        if "messages" not in st.session_state:
            st.session_state.messages = [{
                "role": "assistant",
                "content": "¡Hola! He cargado los documentos de tu carpeta de Drive. ¿Qué te gustaría saber?"
            }]

        # Mostrar mensajes
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Input del usuario
        if prompt := st.chat_input("Haz una pregunta sobre tus documentos..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    response = generate_response(prompt, document_context)
                    st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        st.warning("No se pudo cargar contenido de la carpeta de Google Drive o la carpeta está vacía.")
    
