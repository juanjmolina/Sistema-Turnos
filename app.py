"""
app.py — Sistema de Turnos y Compensatorios
============================================
Punto de entrada. Sirve el HTML original sin modificarlo.
Toda la interfaz visual, lógica de negocio y comportamiento
permanece EXACTAMENTE igual al archivo index.html original.
Python solo gestiona la persistencia (SQLite/PostgreSQL).
"""
import os
import json
import streamlit as st
import streamlit.components.v1 as components

from database.db import init_db, guardar_snapshot, cargar_snapshot, registrar_log
from modules.ui_helpers import pagina_config, ocultar_streamlit_ui
from modules.logic import leer_html, construir_js_sync

# ── Configuración de página (debe ser la primera llamada a st) ─
pagina_config()
ocultar_streamlit_ui()

# ── Inicializar base de datos (crea tablas si no existen) ─────
init_db()

# ── Procesar datos entrantes via query params ─────────────────
# El JS del frontend envía los datos como ?_save=<json_encoded>
params = st.query_params
if "_save" in params:
    try:
        raw   = params["_save"]
        datos = json.loads(raw)
        # Extraer usuario si viene en el payload
        usuario = datos.pop("__usuario__", "web")
        ok = guardar_snapshot("sistema_turnos_v1", datos, usuario)
        if ok:
            registrar_log(usuario, "guardar:sistema_turnos_v1")
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        # No mostrar errores al usuario final — solo loguear
        print(f"[app] Error al procesar _save: {e}")

# ── Cargar snapshot más reciente desde la BD ──────────────────
snapshot = cargar_snapshot("sistema_turnos_v1")

# ── Construir HTML final (original + script de sincronización) ─
html = leer_html()
html = construir_js_sync(html, snapshot)

# ── Renderizar la aplicación completa ─────────────────────────
# height=960 da espacio generoso; scrolling=True permite scroll interno
components.html(html, height=960, scrolling=True)
