"""
modules/ui_helpers.py
=====================
Helpers de configuración de Streamlit.
Solo oculta los elementos nativos de Streamlit para que
la interfaz muestre ÚNICAMENTE el HTML original.
"""
import streamlit as st

def pagina_config():
    """Configura la página de Streamlit."""
    st.set_page_config(
        page_title="Sistema de Turnos",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

def ocultar_streamlit_ui():
    """
    Oculta completamente la UI de Streamlit (menú, footer, header, toolbar).
    El usuario solo ve el HTML del sistema.
    """
    st.markdown("""
    <style>
        /* Ocultar toda la interfaz nativa de Streamlit */
        #MainMenu              { display: none !important; }
        footer                 { display: none !important; }
        header                 { display: none !important; }
        [data-testid="stToolbar"]       { display: none !important; }
        [data-testid="stDecoration"]    { display: none !important; }
        [data-testid="stStatusWidget"]  { display: none !important; }
        section[data-testid="stSidebar"]{ display: none !important; }

        /* Eliminar padding y márgenes de Streamlit */
        .block-container {
            padding: 0 !important;
            max-width: 100% !important;
            margin: 0 !important;
        }
        [data-testid="stAppViewContainer"] > div {
            padding: 0 !important;
        }
        [data-testid="stVerticalBlock"] {
            gap: 0 !important;
            padding: 0 !important;
        }
        /* Iframe ocupa toda la pantalla */
        iframe {
            border: none !important;
            display: block !important;
        }
    </style>
    """, unsafe_allow_html=True)
