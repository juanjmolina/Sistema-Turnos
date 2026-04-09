"""
modules/ui_helpers.py
Componentes reutilizables de UI para Streamlit.
"""
import streamlit as st
from modules.logic import TIPOS_AUS_MAP, ESTADOS_AUS, fmt_full_es


# ── Badges HTML inline ─────────────────────────────────────────

def badge_turno(turno: dict) -> str:
    return (
        f'<span style="background:{turno["bg"]};color:{turno["text"]};'
        f'border-radius:6px;padding:3px 10px;font-weight:700;font-size:12px">'
        f'{turno["nombre"]} · {turno["horario"]}</span>'
    )


def badge_estado(estado: str) -> str:
    styles = {
        "Aprobado":  ("background:#D1FAE5;color:#065F46", "✅"),
        "Pendiente": ("background:#FEF3C7;color:#92400E", "⏳"),
        "Rechazado": ("background:#FEE2E2;color:#991B1B", "❌"),
    }
    sty, icon = styles.get(estado, ("background:#F1F5F9;color:#475569", "•"))
    return (
        f'<span style="{sty};border-radius:12px;padding:2px 10px;'
        f'font-weight:700;font-size:11px">{icon} {estado}</span>'
    )


def badge_grupo(grupo: str) -> str:
    colors = {"A": "#1E3A8A", "B": "#0F766E", "C": "#7C3AED"}
    c = colors.get(grupo, "#475569")
    return (
        f'<span style="background:{c};color:#fff;border-radius:5px;'
        f'padding:2px 8px;font-weight:700;font-size:11px">Grupo {grupo}</span>'
    )


def badge_tipo_aus(tipo_id: str) -> str:
    t = TIPOS_AUS_MAP.get(tipo_id, {"label": tipo_id, "color": "#475569", "bg": "#F1F5F9", "icon": "•"})
    return (
        f'<span style="background:{t["bg"]};color:{t["color"]};'
        f'border-radius:6px;padding:2px 9px;font-weight:700;font-size:11px">'
        f'{t["icon"]} {t["label"]}</span>'
    )


# ── Metric cards ───────────────────────────────────────────────

def stat_card(label: str, value, color: str = "#1E3A8A", suffix: str = ""):
    st.markdown(
        f"""
        <div style="background:#fff;border-radius:10px;padding:14px 16px;
                    box-shadow:0 1px 6px rgba(0,0,0,.08);
                    border-left:4px solid {color};text-align:center">
            <div style="font-size:1.8rem;font-weight:800;color:{color}">{value}{suffix}</div>
            <div style="font-size:.72rem;color:#64748B;margin-top:2px">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Sección de encabezado ──────────────────────────────────────

def section_header(title: str, subtitle: str = "", gradient: str = "135deg,#1E3A8A,#3B82F6"):
    st.markdown(
        f"""
        <div style="background:linear-gradient({gradient});border-radius:14px;
                    padding:18px 24px;color:#fff;margin-bottom:16px">
            <h2 style="margin:0;font-size:1.2rem;font-weight:800">{title}</h2>
            {"<p style='margin:4px 0 0;font-size:.8rem;opacity:.85'>"+subtitle+"</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Tabla de ausencias ─────────────────────────────────────────

def render_ausencia_row(a: dict, on_edit=None, on_delete=None):
    """Renderiza una fila de ausencia con botones de acción."""
    tipo = TIPOS_AUS_MAP.get(a.get("tipo", ""), {"label": a.get("tipo", ""), "icon": "•"})
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
    with col1:
        st.markdown(
            f'**{a.get("worker_nombre", "")}** {badge_grupo(a.get("worker_grupo", ""))}',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'{tipo["icon"]} {tipo["label"]}', unsafe_allow_html=True
        )
    with col3:
        fi = fmt_full_es(a.get("fecha_inicio", ""))
        ff = fmt_full_es(a.get("fecha_fin", ""))
        st.caption(f"{fi} → {ff}")
    with col4:
        st.markdown(badge_estado(a.get("estado", "Pendiente")), unsafe_allow_html=True)
    with col5:
        if on_edit:
            if st.button("✏️", key=f"edit_aus_{a['id']}", help="Editar"):
                on_edit(a)
        if on_delete:
            if st.button("🗑️", key=f"del_aus_{a['id']}", help="Eliminar"):
                on_delete(a["id"])


# ── Empty state ────────────────────────────────────────────────

def empty_state(icon: str = "📭", message: str = "Sin registros"):
    st.markdown(
        f"""
        <div style="text-align:center;padding:40px;color:#94A3B8">
            <div style="font-size:2.5rem;margin-bottom:8px">{icon}</div>
            <div style="font-size:.9rem">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Confirmación de eliminación ────────────────────────────────

def confirm_delete_dialog(key: str, message: str = "¿Eliminar este registro?") -> bool:
    """
    Muestra un expander de confirmación. Retorna True cuando el usuario confirma.
    Usar: if confirm_delete_dialog("key"): ...
    """
    with st.expander(f"⚠️ {message}", expanded=False):
        st.warning(message)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", key=f"confirm_{key}", type="primary"):
                return True
        with col2:
            if st.button("Cancelar", key=f"cancel_{key}"):
                pass
    return False


# ── Paginación simple ──────────────────────────────────────────

def paginate(items: list, page_size: int = 20, key: str = "page") -> list:
    total = len(items)
    if total <= page_size:
        return items
    total_pages = (total - 1) // page_size + 1
    page = st.number_input(
        f"Página (de {total_pages})", min_value=1, max_value=total_pages,
        value=1, key=key
    )
    start = (page - 1) * page_size
    return items[start: start + page_size]


# ── Filtro de búsqueda ─────────────────────────────────────────

def search_filter(items: list, fields: list[str], placeholder: str = "🔍 Buscar...") -> list:
    q = st.text_input("", placeholder=placeholder, key=f"search_{'_'.join(fields)}", label_visibility="collapsed")
    if not q:
        return items
    q = q.lower()
    return [
        item for item in items
        if any(q in str(item.get(f, "")).lower() for f in fields)
    ]
