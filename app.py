# app.py

import os
import json
import re
import streamlit as st
import google.generativeai as genai

# --- Configuración de la Página y Título ---
st.set_page_config(
    page_title="Chat con Documentación",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Chat con Documentación usando Gemini")
st.caption("Selecciona un grupo de documentos en la barra lateral y haz preguntas sobre ellos.")

# --- Constantes y Datos Iniciales (como en el código TSX) ---
GEMINI_DOCS_URLS = [
    "https://ai.google.dev/gemini-api/docs",
    "https://ai.google.dev/gemini-api/docs/quickstart",
    "https://ai.google.dev/gemini-api/docs/models",
    "https://ai.google.dev/gemini-api/docs/pricing",
]

MODEL_CAPABILITIES_URLS = [
    "https://ai.google.dev/gemini-api/docs/text-generation",
    "https://ai.google.dev/gemini-api/docs/image-generation",
    "https://ai.google.dev/gemini-api/docs/function-calling",
    "https://ai.google.dev/gemini-api/docs/grounding",
]

INITIAL_URL_GROUPS = {
    'gemini-overview': {'name': 'Gemini Docs Overview', 'urls': GEMINI_DOCS_URLS},
    'model-capabilities': {'name': 'Model Capabilities', 'urls': MODEL_CAPABILITIES_URLS},
}

# --- Configuración de la API de Gemini ---
# NOTA DE SEGURIDAD: Usamos st.secrets para el despliegue en Streamlit Community Cloud.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    API_KEY_CONFIGURED = True
except (KeyError, FileNotFoundError):
    API_KEY_CONFIGURED = False
    st.error("🚨 Error: La API Key de Gemini no está configurada.")
    st.warning("Para usar la app, configura tu API Key como un 'Secret' en Streamlit Community Cloud con el nombre `GEMINI_API_KEY`.")

# Modelo generativo de Gemini
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Funciones de Lógica de la Aplicación (equivalente a geminiService) ---

def get_initial_suggestions(urls: list[str]) -> list[str]:
    """Genera sugerencias de preguntas iniciales basadas en las URLs."""
    if not urls:
        return []
    
    prompt = f"""
    Basado en el contenido potencial de las siguientes URLs, genera una lista de 3 preguntas interesantes y concisas que un usuario podría hacer.
    URLs: {', '.join(urls)}
    
    Devuelve SOLAMENTE un objeto JSON con una clave "suggestions" que contenga una lista de strings.
    Ejemplo de formato:
    ```json
    {{
      "suggestions": [
        "¿Cuáles son los modelos de Gemini disponibles?",
        "¿Cómo funciona el grounding?",
        "Explica los precios de la API."
      ]
    }}
    ```
    """
    try:
        response = model.generate_content(prompt)
        # Limpiar la respuesta para extraer solo el JSON (como en el código TSX)
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.text)
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            return data.get("suggestions", [])
        return []
    except Exception as e:
        print(f"Error generando sugerencias: {e}")
        return []

def generate_response(query: str, urls: list[str]) -> str:
    """Genera una respuesta del chat usando el contexto de las URLs."""
    prompt = f"""
    Eres un asistente experto en la documentación de Google.
    Usando el contenido de las siguientes URLs como contexto principal, responde la pregunta del usuario.
    Si la respuesta no se encuentra en el contexto, indícalo.
    
    Contexto de URLs:
    {', '.join(urls)}
    
    Pregunta del usuario:
    "{query}"
    
    Respuesta:
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error al generar la respuesta: {e}"


# --- Estado de la Sesión (equivalente a useState) ---
# Usamos st.session_state para mantener el estado entre interacciones del usuario.

if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_group_id" not in st.session_state:
    st.session_state.active_group_id = list(INITIAL_URL_GROUPS.keys())[0]
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []
if "last_fetched_group_id" not in st.session_state:
    st.session_state.last_fetched_group_id = None

# --- Barra Lateral (KnowledgeBaseManager) ---
with st.sidebar:
    st.header("📚 Base de Conocimiento")
    
    # Selector para el grupo de URLs
    group_options = {id: data['name'] for id, data in INITIAL_URL_GROUPS.items()}
    selected_group_id = st.radio(
        "Selecciona un grupo de documentos:",
        options=group_options.keys(),
        format_func=lambda id: group_options[id],
        key='active_group_id' # Vinculamos el radio button al estado de sesión
    )
    
    active_group_name = INITIAL_URL_GROUPS[st.session_state.active_group_id]['name']
    st.write(f"**Grupo Activo:** {active_group_name}")
    
    # Mostrar las URLs del grupo activo
    with st.expander("Ver URLs del grupo"):
        urls_in_group = INITIAL_URL_GROUPS[st.session_state.active_group_id]['urls']
        for url in urls_in_group:
            st.markdown(f"- `{url}`")

# --- Lógica Principal ---

# Detectar si el grupo de URLs ha cambiado para resetear el chat y las sugerencias
if st.session_state.active_group_id != st.session_state.last_fetched_group_id:
    st.session_state.messages = [{
        "role": "assistant",
        "content": f"¡Hola! Ahora estás chateando con la documentación de '{active_group_name}'. ¿En qué puedo ayudarte?"
    }]
    st.session_state.suggestions = [] # Limpiar sugerencias viejas
    st.session_state.last_fetched_group_id = st.session_state.active_group_id
    # Forzar un rerun para que las sugerencias se carguen
    st.rerun()

# Cargar sugerencias si no existen para el grupo actual
if not st.session_state.suggestions and API_KEY_CONFIGURED:
    with st.spinner("Generando sugerencias..."):
        current_urls = INITIAL_URL_GROUPS[st.session_state.active_group_id]['urls']
        st.session_state.suggestions = get_initial_suggestions(current_urls)
        # Forzar un rerun para mostrar las sugerencias
        st.rerun()

# --- Interfaz de Chat (ChatInterface) ---

# Mostrar mensajes existentes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Mostrar sugerencias como botones clickables
if st.session_state.suggestions and len(st.session_state.messages) <= 1:
    cols = st.columns(len(st.session_state.suggestions))
    for i, suggestion in enumerate(st.session_state.suggestions):
        with cols[i]:
            if st.button(suggestion, key=f"suggestion_{i}"):
                # Al hacer clic, se usará este texto como prompt
                user_prompt = suggestion
                st.session_state.suggestions = [] # Ocultar sugerencias
                break
    else:
        user_prompt = None
else:
    user_prompt = None

# Input del usuario en el chat
chat_input_disabled = not API_KEY_CONFIGURED
if prompt_from_chat := st.chat_input("Haz una pregunta sobre la documentación...", disabled=chat_input_disabled):
    user_prompt = prompt_from_chat

# Procesar y mostrar la respuesta si hay un nuevo prompt
if user_prompt:
    st.session_state.suggestions = [] # Ocultar sugerencias después de la primera pregunta
    
    # Añadir mensaje del usuario al historial y mostrarlo
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)
        
    # Generar y mostrar respuesta del asistente
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            current_urls = INITIAL_URL_GROUPS[st.session_state.active_group_id]['urls']
            response = generate_response(user_prompt, current_urls)
            st.markdown(response)
    
    # Añadir respuesta del asistente al historial
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()