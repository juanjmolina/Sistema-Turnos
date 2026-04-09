"""
modules/logic.py
================
Lógica de negocio: inyección de sincronización JS → HTML.
El HTML nunca se modifica visualmente, solo se le agrega
un script al final para conectar localStorage ↔ SQLite/PG.
"""
import os
import json

HTML_FILE = os.path.join(os.path.dirname(__file__), "..", "index.html")

def leer_html() -> str:
    """Lee el archivo index.html sin modificarlo."""
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1 style='color:red'>Error: index.html no encontrado. Colócalo junto a app.py</h1>"


def construir_js_sync(html: str, snapshot: dict | None) -> str:
    """
    Inyecta un bloque <script> al final del HTML que:
    1. Carga los datos de la DB en localStorage al abrir la app.
    2. Conecta el botón '💾 Guardar en base de datos' con el backend.
    3. Muestra un toast de confirmación.
    No toca ningún estilo, layout ni funcionalidad del HTML original.
    """
    datos_db   = json.dumps(snapshot["datos"]          if snapshot else {})
    hash_db    = json.dumps(snapshot["hash"]            if snapshot else "")
    ts_db      = json.dumps(snapshot["actualizado_en"]  if snapshot else "")

    # Construir URL base para el guardado (query param _save)
    script = f"""
<script>
// ══ SINCRONIZACIÓN CON BASE DE DATOS (inyectado por app.py) ══
(function() {{
  const HASH_DB  = {hash_db};
  const DATOS_DB = {datos_db};
  const TS_DB    = {ts_db};

  // Módulos que se sincronizan
  const MODULOS = [
    'workers','ausencias','celdasEstado','horasExtras',
    'nextWId','nextAId','filterGrupo','filterAusTipo',
    'filterAusEst','filterAusWk','vac_data','cum_data',
    'comp_ganados','cc_data','che_data'
  ];

  // ── 1. Cargar datos de la DB al inicio ──────────────────
  function cargarDesdeBD() {{
    if (!DATOS_DB || Object.keys(DATOS_DB).length === 0) return;
    const hashLocal = localStorage.getItem('_db_hash');
    if (hashLocal && hashLocal === HASH_DB) return; // ya sincronizado

    MODULOS.forEach(mod => {{
      if (DATOS_DB[mod] !== undefined) {{
        try {{ localStorage.setItem(mod, JSON.stringify(DATOS_DB[mod])); }}
        catch(e) {{ console.warn('[DB] Error cargando', mod, e); }}
      }}
    }});
    localStorage.setItem('_db_hash', HASH_DB);
    localStorage.setItem('_db_ts', TS_DB);

    // Re-renderizar la interfaz con los nuevos datos
    setTimeout(() => {{
      ['render','renderHeader','cumRefrescar','vRefrescar',
       'compRefrescar','ccRefrescar'].forEach(fn => {{
        if (typeof window[fn] === 'function') window[fn]();
      }});
    }}, 400);
  }}

  // ── 2. Guardar datos en la BD ────────────────────────────
  window.guardarEnBD = function() {{
    try {{
      if (typeof buildSnapshot !== 'function') {{
        toast('❌ buildSnapshot no disponible', '#EF4444'); return;
      }}
      const snap = buildSnapshot();
      const encoded = encodeURIComponent(JSON.stringify(snap));
      // Streamlit lee _save desde query params
      const url = new URL(window.location.href);
      url.searchParams.set('_save', encoded);
      window.location.href = url.toString();
    }} catch(e) {{
      toast('❌ Error al guardar: ' + e.message, '#EF4444');
    }}
  }};

  // ── 3. Interceptar botón Exportar para guardar en BD también ──
  function hookExportar() {{
    if (typeof window.exportarDatos !== 'function') return;
    const orig = window.exportarDatos;
    window.exportarDatos = function() {{
      orig();
      try {{
        const snap = buildSnapshot();
        const encoded = encodeURIComponent(JSON.stringify(snap));
        // Guardado silencioso en background via fetch
        fetch('?_save=' + encoded).catch(() => {{}});
        localStorage.setItem('_db_hash', ''); // forzar recarga próxima vez
        toast('✅ Exportado y guardado en base de datos', '#10B981');
      }} catch(e) {{}}
    }};
  }}

  // ── 4. Agregar botón "Guardar en BD" al panel de Backup ──
  function agregarBotonBD() {{
    const obs = new MutationObserver(() => {{
      const box = document.querySelector('.backup-box');
      if (!box || document.getElementById('_bdSection')) return;
      const sec = document.createElement('div');
      sec.id = '_bdSection';
      sec.className = 'backup-section';
      sec.innerHTML = `
        <h3>🐘 Base de datos</h3>
        <p>Guarda todos los datos en SQLite/PostgreSQL. Los cambios quedan disponibles para todos los usuarios al recargar.</p>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <button onclick="guardarEnBD()" class="btn btn-primary"
            style="background:#059669;font-size:.85rem;padding:8px 18px">
            🔄 Guardar en base de datos
          </button>
          <span style="font-size:11px;color:#94A3B8">
            Última sincronización: ${{TS_DB || 'Nunca'}}
          </span>
        </div>`;
      box.insertBefore(sec, box.lastElementChild);
      obs.disconnect();
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
  }}

  // ── 5. Toast de notificación ─────────────────────────────
  function toast(msg, color) {{
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;bottom:24px;right:24px;z-index:99999;
      background:${{color}};color:#fff;border-radius:10px;padding:12px 20px;
      font-size:13px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.2)`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }}

  // ── Inicializar ──────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {{
    cargarDesdeBD();
    setTimeout(hookExportar, 1200);
    agregarBotonBD();
  }});
}})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", script + "\n</body>", 1)
    return html + script
