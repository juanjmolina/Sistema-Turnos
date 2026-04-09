"""
app.py — Sistema de Turnos + Compensatorios
Punto de entrada principal de la aplicación Streamlit.
"""
import streamlit as st
from datetime import date, timedelta
import pandas as pd
import io

# ── Configuración de página ────────────────────────────────────
st.set_page_config(
    page_title="Sistema de Turnos",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inicialización ─────────────────────────────────────────────
from database.db import init_db, verificar_usuario
init_db()

from modules.logic import (
    TURNOS, GRUPOS, DIAS, TIPOS_HE, TIPOS_AUS, TIPOS_AUS_MAP,
    ESTADOS_AUS, MAQUINAS_LIST, MESES_ES,
    get_monday, get_rot_week, get_turno, get_turno_info,
    get_week_dates, week_label, get_periodo_info,
    total_he_worker, empty_he, days_between,
    worker_is_absent, cumpleaños_hoy, cumpleaños_proximos,
    parse_fecha_cumpleaños, vacacion_vencida, dias_vacacion,
    fmt_full_es, fmt_date_es, norm_nombre,
    calcular_comp_disponibles, HE_IDS,
)
from modules.ui_helpers import (
    badge_turno, badge_estado, badge_grupo, badge_tipo_aus,
    stat_card, section_header, empty_state, search_filter, paginate,
)
import database.db as db


# ══════════════════════════════════════════════════════════════
#  CSS GLOBAL
# ══════════════════════════════════════════════════════════════

st.markdown("""
<style>
.stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 14px; }
.stDataFrame { border-radius: 10px; }
div[data-testid="metric-container"] {
    background: #fff;
    border-radius: 10px;
    padding: 12px 16px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08);
    border-left: 4px solid #1E3A8A;
}
.block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════

def login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1E3A8A,#3B82F6);
                    border-radius:18px;padding:40px 36px;text-align:center;
                    color:#fff;margin-top:60px">
            <div style="font-size:3rem">🏭</div>
            <h2 style="margin:8px 0 4px;font-size:1.3rem">Sistema de Turnos</h2>
            <p style="opacity:.85;font-size:.85rem;margin-bottom:28px">
                Ingresa tus credenciales para continuar
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            usuario = st.text_input("👤 Usuario", placeholder="usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar →", use_container_width=True, type="primary")
            if submitted:
                user = verificar_usuario(usuario, password)
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["usuario"] = user["username"]
                    st.session_state["rol"] = user["rol"]
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

        st.caption("Sistema de Turnos · v3.0 · SQLite")


# ══════════════════════════════════════════════════════════════
#  MÓDULO: TURNOS
# ══════════════════════════════════════════════════════════════

def app_turnos():
    if "week_offset" not in st.session_state:
        st.session_state.week_offset = 0

    # Header con navegación de semana
    monday = get_monday(st.session_state.week_offset)
    rot_w  = get_rot_week(monday)
    dates  = get_week_dates(monday)
    info   = get_periodo_info(st.session_state.week_offset)

    # Encabezado
    turnos_grupos = {g: get_turno(g, rot_w) for g in GRUPOS}
    badges = " ".join(
        f'<span style="background:rgba(255,255,255,.15);border-radius:8px;padding:5px 12px;'
        f'font-size:12px;margin-right:4px"><b>Grupo {g}</b> · {turnos_grupos[g]["nombre"]} · {turnos_grupos[g]["horario"]}</span>'
        for g in GRUPOS
    )

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1E3A8A,#3B82F6);border-radius:14px;
                padding:18px 24px;color:#fff;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
            <div>
                <h2 style="margin:0;font-size:1.1rem;font-weight:800">🏭 Sistema de Turnos</h2>
                <p style="margin:4px 0 0;opacity:.85;font-size:.78rem">
                    {week_label(st.session_state.week_offset)} ·
                    {fmt_date_es(dates[0])} – {fmt_date_es(dates[6])} ·
                    {info["label_semana"]} · próximo cambio en {info["dias_para_cambio"]} días
                </p>
            </div>
        </div>
        <div style="margin-top:10px">{badges}</div>
    </div>
    """, unsafe_allow_html=True)

    # Navegación
    c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
    with c1:
        if st.button("⬅️ Anterior", use_container_width=True):
            st.session_state.week_offset -= 1
            st.rerun()
    with c2:
        if st.button("Hoy", use_container_width=True):
            st.session_state.week_offset = 0
            st.rerun()
    with c5:
        if st.button("Siguiente ➡️", use_container_width=True):
            st.session_state.week_offset += 1
            st.rerun()

    # Datos
    workers   = db.get_all_workers()
    ausencias = db.get_all_ausencias()
    week_iso  = monday.isoformat()

    # Tabs principales
    tab_tabla, tab_he, tab_aus, tab_gestionar, tab_backup = st.tabs(
        ["📅 Tabla de Turnos", "⏱️ Horas Extras", "📋 Ausencias", "👥 Gestionar Operarios", "💾 Backup"]
    )

    # ── Tab: Tabla de Turnos ──────────────────────────────────
    with tab_tabla:
        # Filtros
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            busqueda = st.text_input("🔍 Buscar operario o máquina", key="search_tabla", label_visibility="collapsed", placeholder="🔍 Buscar operario o máquina...")
        with col_f2:
            filtro_grupo = st.selectbox("Grupo", ["Todos"] + GRUPOS, key="filtro_grupo", label_visibility="collapsed")

        workers_f = [
            w for w in workers
            if (filtro_grupo == "Todos" or w["grupo"] == filtro_grupo)
            and (not busqueda or busqueda.lower() in (w["nombre"] + w.get("maquina", "")).lower())
        ]

        # Tabla de turnos
        if not workers_f:
            empty_state("👥", "No hay operarios que coincidan con el filtro")
        else:
            # Encabezado de tabla
            headers = ["Operario", "Máquina", "Grp"] + [
                f"{DIAS[i]}\n{fmt_date_es(d)}" for i, d in enumerate(dates)
            ] + ["Ausencias"]

            rows = []
            for w in workers_f:
                t_base = get_turno(w["grupo"], rot_w)
                row = {
                    "Operario": w["nombre"],
                    "Máquina": w.get("maquina") or "—",
                    "Grupo": f"Gpo {w['grupo']}",
                }
                for idx, d in enumerate(dates):
                    t_info = get_turno_info(t_base, idx)
                    aus = worker_is_absent(ausencias, w["id"], d)
                    if aus:
                        tipo = TIPOS_AUS_MAP.get(aus["tipo"], {"label": aus["tipo"], "icon": "•"})
                        row[DIAS[idx]] = f'{tipo["icon"]} {tipo["label"][:8]}'
                    elif t_info["descanso"]:
                        row[DIAS[idx]] = "😴 Descanso"
                    else:
                        row[DIAS[idx]] = f'{t_info["nombre"]} {t_info["horario"]}'

                # Contar ausencias semana
                aus_sem = len([a for a in ausencias if a["worker_id"] == w["id"]
                               and a["fecha_inicio"] <= dates[6].isoformat()
                               and a["fecha_fin"] >= dates[0].isoformat()])
                row["Aus."] = aus_sem if aus_sem else "—"
                rows.append(row)

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Tab: Horas Extras ─────────────────────────────────────
    with tab_he:
        st.markdown("### ⏱️ Horas Extras de la semana")

        col_h1, col_h2, col_h3, col_h4 = st.columns(4)
        all_he_data = [db.get_horas_extras(w["id"], week_iso) for w in workers]
        total_he_all = sum(total_he_worker(he) for he in all_he_data)
        workers_con_he = sum(1 for he in all_he_data if total_he_worker(he) > 0)
        with col_h1:
            st.metric("Total HE semana", f"{total_he_all:.1f}h")
        with col_h2:
            st.metric("Operarios con HE", workers_con_he)
        with col_h3:
            st.metric("Límite semanal", f"{LIMITE_SEMANAL}h")
        with col_h4:
            st.metric("Límite diario", f"{LIMITE_DIARIO}h")

        st.divider()

        search_he = st.text_input("🔍 Buscar operario", key="search_he", label_visibility="collapsed", placeholder="🔍 Buscar...")
        workers_he = [w for w in workers if not search_he or search_he.lower() in w["nombre"].lower()]

        for w in workers_he:
            he = db.get_horas_extras(w["id"], week_iso)
            total = total_he_worker(he)
            alerta = total > LIMITE_SEMANAL

            with st.expander(
                f'{"🔴" if alerta else "🟡" if total > 0 else "⚪"} '
                f'{w["nombre"]} — Grupo {w["grupo"]} — '
                f'**{total:.1f}h** {"⚠️ Límite excedido" if alerta else ""}',
                expanded=total > 0,
            ):
                cols_he = st.columns(len(TIPOS_HE))
                he_updated = dict(he)
                changed = False
                for i, tipo in enumerate(TIPOS_HE):
                    with cols_he[i]:
                        st.markdown(
                            f'<div style="text-align:center;background:{tipo["bg"]};'
                            f'border-radius:7px;padding:6px 4px;margin-bottom:4px">'
                            f'<span style="font-size:1.1rem">{tipo["icon"]}</span><br>'
                            f'<span style="font-size:.65rem;font-weight:700;color:{tipo["color"]}">'
                            f'{tipo["label"][:15]}<br>+{tipo["recargo"]}%</span></div>',
                            unsafe_allow_html=True,
                        )
                        new_val = st.number_input(
                            "h", min_value=0.0, max_value=float(LIMITE_SEMANAL),
                            value=float(he.get(tipo["id"], 0)),
                            step=0.5, key=f"he_{w['id']}_{tipo['id']}_{week_iso}",
                            label_visibility="collapsed",
                        )
                        if new_val != he.get(tipo["id"], 0):
                            he_updated[tipo["id"]] = new_val
                            changed = True

                if changed:
                    db.set_horas_extras(w["id"], week_iso, he_updated)
                    st.rerun()

    # ── Tab: Ausencias ────────────────────────────────────────
    with tab_aus:
        st.markdown("### 📋 Ausencias")

        # Filtros
        c1, c2, c3 = st.columns(3)
        with c1:
            f_tipo = st.selectbox(
                "Tipo", ["Todos"] + [t["label"] for t in TIPOS_AUS], key="f_aus_tipo"
            )
        with c2:
            f_estado = st.selectbox("Estado", ["Todos"] + ESTADOS_AUS, key="f_aus_est")
        with c3:
            f_grupo_aus = st.selectbox("Grupo", ["Todos"] + GRUPOS, key="f_aus_grp")

        ausencias_all = db.get_all_ausencias()

        # Aplicar filtros
        aus_f = ausencias_all
        if f_tipo != "Todos":
            aus_f = [a for a in aus_f if TIPOS_AUS_MAP.get(a["tipo"], {}).get("label") == f_tipo]
        if f_estado != "Todos":
            aus_f = [a for a in aus_f if a["estado"] == f_estado]
        if f_grupo_aus != "Todos":
            aus_f = [a for a in aus_f if a.get("worker_grupo") == f_grupo_aus]

        # Stats
        ca, cb, cc, cd = st.columns(4)
        with ca: st.metric("Total", len(aus_f))
        with cb: st.metric("Aprobadas", sum(1 for a in aus_f if a["estado"] == "Aprobado"))
        with cc: st.metric("Pendientes", sum(1 for a in aus_f if a["estado"] == "Pendiente"))
        with cd: st.metric("Rechazadas", sum(1 for a in aus_f if a["estado"] == "Rechazado"))

        st.divider()

        # Formulario nueva ausencia
        with st.expander("➕ Registrar nueva ausencia", expanded=False):
            with st.form("form_ausencia", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    w_opts = {f"{w['nombre']} (Grupo {w['grupo']})": w["id"] for w in workers}
                    w_sel = st.selectbox("👤 Operario *", list(w_opts.keys()))
                    tipo_sel = st.selectbox(
                        "📌 Tipo de ausencia *",
                        [t["label"] for t in TIPOS_AUS]
                    )
                    obs = st.text_area("Observación", height=60)
                with c2:
                    fi = st.date_input("📅 Fecha inicio *", value=date.today())
                    ff = st.date_input("📅 Fecha fin *", value=date.today())
                    est_sel = st.selectbox("Estado", ESTADOS_AUS)

                submit_aus = st.form_submit_button("💾 Guardar ausencia", type="primary")
                if submit_aus:
                    if ff < fi:
                        st.error("La fecha fin no puede ser anterior a la fecha inicio.")
                    else:
                        tipo_id = next(t["id"] for t in TIPOS_AUS if t["label"] == tipo_sel)
                        db.create_ausencia(
                            worker_id=w_opts[w_sel],
                            tipo=tipo_id,
                            fecha_inicio=fi.isoformat(),
                            fecha_fin=ff.isoformat(),
                            estado=est_sel,
                            observacion=obs,
                        )
                        st.success("✅ Ausencia registrada")
                        st.rerun()

        # Lista de ausencias
        if not aus_f:
            empty_state("📭", "No hay ausencias con los filtros seleccionados")
        else:
            for a in paginate(aus_f, page_size=15, key="pag_aus"):
                tipo = TIPOS_AUS_MAP.get(a.get("tipo", ""), {"label": a.get("tipo",""), "icon":"•"})
                dias = days_between(a["fecha_inicio"], a["fecha_fin"])
                with st.container():
                    c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 1, 1])
                    with c1:
                        st.markdown(
                            f'**{a.get("worker_nombre","")}** '
                            f'{badge_grupo(a.get("worker_grupo",""))}',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        st.markdown(
                            f'{tipo["icon"]} {tipo["label"]}', unsafe_allow_html=True
                        )
                    with c3:
                        st.caption(f'{fmt_full_es(a["fecha_inicio"])} → {fmt_full_es(a["fecha_fin"])} ({dias}d)')
                    with c4:
                        # Cambio de estado rápido
                        new_est = st.selectbox(
                            "Estado",
                            ESTADOS_AUS,
                            index=ESTADOS_AUS.index(a["estado"]),
                            key=f"est_{a['id']}",
                            label_visibility="collapsed",
                        )
                        if new_est != a["estado"]:
                            db.update_ausencia_estado(a["id"], new_est)
                            st.rerun()
                    with c5:
                        st.caption(f'Obs: {a.get("observacion","") or "—"}')
                    with c6:
                        if st.button("🗑️", key=f"del_a_{a['id']}", help="Eliminar"):
                            db.delete_ausencia(a["id"])
                            st.rerun()
                    st.divider()

    # ── Tab: Gestionar Operarios ──────────────────────────────
    with tab_gestionar:
        st.markdown("### 👥 Gestionar Operarios")

        with st.expander("➕ Agregar nuevo operario", expanded=False):
            with st.form("form_worker", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nombre_w = st.text_input("👤 Nombre *")
                with c2:
                    grupo_w = st.selectbox("Grupo *", GRUPOS)
                with c3:
                    maq_w = st.selectbox("Máquina", [""] + MAQUINAS_LIST)
                if st.form_submit_button("Agregar", type="primary"):
                    if nombre_w.strip():
                        db.create_worker(nombre_w, grupo_w, maq_w)
                        st.success(f"✅ {nombre_w} agregado al Grupo {grupo_w}")
                        st.rerun()
                    else:
                        st.error("El nombre es obligatorio.")

        # Tabla de operarios con edición y eliminación
        workers_all = db.get_all_workers()
        buscar_w = st.text_input("🔍 Buscar", key="srch_workers", label_visibility="collapsed", placeholder="🔍 Buscar operario...")
        workers_vis = [w for w in workers_all if not buscar_w or buscar_w.lower() in w["nombre"].lower()]

        for w in workers_vis:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 1, 1])
                with c1:
                    st.markdown(f'**{w["nombre"]}**')
                with c2:
                    st.markdown(badge_grupo(w["grupo"]), unsafe_allow_html=True)
                with c3:
                    st.caption(w.get("maquina") or "Sin máquina")
                with c4:
                    if st.button("✏️ Editar", key=f"edit_w_{w['id']}"):
                        st.session_state[f"editing_worker"] = w["id"]
                with c5:
                    if st.button("🗑️", key=f"del_w_{w['id']}"):
                        db.delete_worker(w["id"])
                        st.rerun()

                # Formulario de edición inline
                if st.session_state.get("editing_worker") == w["id"]:
                    with st.form(f"form_edit_w_{w['id']}"):
                        cn1, cn2, cn3 = st.columns(3)
                        with cn1:
                            new_nombre = st.text_input("Nombre", value=w["nombre"])
                        with cn2:
                            new_grupo = st.selectbox("Grupo", GRUPOS, index=GRUPOS.index(w["grupo"]))
                        with cn3:
                            maq_opts = [""] + MAQUINAS_LIST
                            maq_idx = maq_opts.index(w.get("maquina") or "") if (w.get("maquina") or "") in maq_opts else 0
                            new_maq = st.selectbox("Máquina", maq_opts, index=maq_idx)
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.form_submit_button("💾 Guardar", type="primary"):
                                db.update_worker(w["id"], new_nombre, new_grupo, new_maq)
                                st.session_state.pop("editing_worker", None)
                                st.rerun()
                        with cc2:
                            if st.form_submit_button("Cancelar"):
                                st.session_state.pop("editing_worker", None)
                                st.rerun()

                st.divider()

    # ── Tab: Backup ───────────────────────────────────────────
    with tab_backup:
        section_header("💾 Backup y Restauración", "Exporta o importa los datos de la aplicación")
        st.info("Los datos están guardados en SQLite. El backup JSON es compatible con la versión anterior HTML.")

        col_exp, col_imp = st.columns(2)
        with col_exp:
            st.markdown("#### ⬇️ Exportar datos")
            if st.button("Generar backup JSON", use_container_width=True, type="primary"):
                import json
                workers_data = db.get_all_workers()
                aus_data     = db.get_all_ausencias()
                vac_data_    = db.get_all_vacaciones()
                cum_data_    = db.get_all_cumpleanios()
                snap = {
                    "version": 3,
                    "exportadoEn": date.today().isoformat(),
                    "workers": workers_data,
                    "ausencias": aus_data,
                    "vacaciones": vac_data_,
                    "cumpleanios": cum_data_,
                }
                buf = io.BytesIO(json.dumps(snap, indent=2, default=str).encode())
                st.download_button(
                    "⬇️ Descargar backup",
                    data=buf,
                    file_name=f"backup-turnos-{date.today().isoformat()}.json",
                    mime="application/json",
                    use_container_width=True,
                )

        with col_imp:
            st.markdown("#### ⬆️ Importar datos")
            uploaded = st.file_uploader("Cargar backup JSON", type=["json"])
            if uploaded:
                import json
                try:
                    snap = json.loads(uploaded.read())
                    st.warning("⚠️ Esto reemplazará los datos actuales. Use fusionar para mezclar.")
                    if st.button("Importar backup", type="primary"):
                        st.info("Importación completada. Recarga la página.")
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════
#  MÓDULO: COMPENSATORIOS
# ══════════════════════════════════════════════════════════════

def app_compensatorios():
    section_header("🔄 Compensatorios", "Días CHE ganados por horas extras · saldo y movimientos",
                   gradient="135deg,#1e40af,#3b82f6")

    workers   = db.get_all_workers()
    ausencias = db.get_all_ausencias()

    # Calcular saldos desde ausencias CHE + comp_ganados
    comp_ganados = db.get_all_comp_ganados()
    usados       = calcular_comp_disponibles(ausencias, workers)

    tab_saldo, tab_movs, tab_importar = st.tabs(["💰 Saldos", "📋 Movimientos CHE", "📂 Ganados (importar)"])

    with tab_saldo:
        st.markdown("#### Saldo de días compensatorios por operario")
        buscar_comp = st.text_input("🔍 Buscar", key="src_comp", label_visibility="collapsed", placeholder="🔍 Buscar operario...")
        workers_vis = [w for w in workers if not buscar_comp or buscar_comp.lower() in w["nombre"].lower()]

        if not workers_vis:
            empty_state()
        else:
            rows = []
            for w in workers_vis:
                ganados = comp_ganados.get(w["nombre"], 0)
                usad = usados.get(w["nombre"], 0)
                saldo = ganados - usad
                rows.append({
                    "Operario": w["nombre"],
                    "Grupo": f"Gpo {w['grupo']}",
                    "Ganados (h/días)": f"{ganados:.1f}",
                    "Usados (días CHE)": f"{usad}",
                    "Saldo": f"{saldo:.1f}",
                    "Estado": "✅ OK" if saldo >= 0 else "⚠️ Negativo",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_movs:
        st.markdown("#### Movimientos CHE (ausencias tipo Compensatorio)")
        aus_che = [a for a in ausencias if a.get("tipo") == "CHE"]
        if not aus_che:
            empty_state("🔄", "No hay movimientos CHE registrados")
        else:
            rows_m = []
            for a in aus_che:
                w = next((x for x in workers if x["id"] == a["worker_id"]), None)
                rows_m.append({
                    "Operario": w["nombre"] if w else "—",
                    "Grupo": w["grupo"] if w else "—",
                    "Inicio": fmt_full_es(a["fecha_inicio"]),
                    "Fin": fmt_full_es(a["fecha_fin"]),
                    "Días": days_between(a["fecha_inicio"], a["fecha_fin"]),
                    "Estado": a["estado"],
                    "Observación": a.get("observacion", ""),
                })
            st.dataframe(pd.DataFrame(rows_m), use_container_width=True, hide_index=True)

    with tab_importar:
        st.markdown("#### Importar horas compensatorias ganadas (Excel)")
        st.info("Sube un Excel con columnas: **Nombre** y **Horas ganadas**")
        file_comp = st.file_uploader("Archivo Excel", type=["xlsx", "xls", "csv"], key="comp_upload")
        if file_comp:
            try:
                if file_comp.name.endswith(".csv"):
                    df_comp = pd.read_csv(file_comp)
                else:
                    df_comp = pd.read_excel(file_comp)

                st.dataframe(df_comp.head(), use_container_width=True)
                col_n = st.selectbox("Columna Nombre", df_comp.columns.tolist(), key="comp_col_n")
                col_h = st.selectbox("Columna Horas", df_comp.columns.tolist(), key="comp_col_h")

                if st.button("✅ Importar", type="primary"):
                    ok = 0
                    for _, row_c in df_comp.iterrows():
                        nombre = str(row_c.get(col_n, "")).strip()
                        horas  = float(row_c.get(col_h, 0) or 0)
                        if nombre:
                            db.set_comp_ganados(nombre, horas)
                            ok += 1
                    st.success(f"✅ {ok} registros importados")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════
#  MÓDULO: VACACIONES
# ══════════════════════════════════════════════════════════════

def app_vacaciones():
    section_header("🌴 Gestión de Vacaciones",
                   "Importa el Excel · aprueba períodos · alertas de días acumulados",
                   gradient="135deg,#0f766e,#14b8a6")

    vac_data = db.get_all_vacaciones()

    tab_per, tab_acum, tab_imp = st.tabs(["📋 Períodos", "📆 Días acumulados", "📂 Importar Excel"])

    with tab_per:
        # Alertas ≥15 días acumulados sin vacaciones programadas
        alertas = [v for v in vac_data if v.get("dias_acum", 0) >= 15 and v["estado"] == "Pendiente"]
        if alertas:
            st.warning(f"⚠️ {len(alertas)} operarios con ≥15 días acumulados sin vacaciones aprobadas")

        # Estadísticas
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total", len(vac_data))
        with c2: st.metric("Aprobadas", sum(1 for v in vac_data if v["estado"] == "Aprobada"))
        with c3: st.metric("Pendientes", sum(1 for v in vac_data if v["estado"] == "Pendiente"))
        with c4: st.metric("Cumplidas", sum(1 for v in vac_data if v["estado"] == "Cumplida"))

        # Filtros
        c1, c2 = st.columns(2)
        with c1:
            buscar_v = st.text_input("🔍", key="srch_vac", label_visibility="collapsed", placeholder="🔍 Buscar operario...")
        with c2:
            f_est_v = st.selectbox("Estado", ["Todos", "Aprobada", "Pendiente", "Cumplida"], key="fv_est")

        vac_f = [
            v for v in vac_data
            if (not buscar_v or buscar_v.lower() in v["nombre"].lower())
            and (f_est_v == "Todos" or v["estado"] == f_est_v)
        ]

        if not vac_f:
            empty_state("🌴", "No hay registros de vacaciones")
        else:
            for v in paginate(vac_f, 15, "pag_vac"):
                venc = vacacion_vencida(v)
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
                with c1:
                    st.markdown(f'**{v["nombre"]}**')
                with c2:
                    st.caption(f'{fmt_full_es(v["salida"])} → {fmt_full_es(v["ingreso"])} ({dias_vacacion(v)}d)')
                with c3:
                    opts = ["Aprobada", "Pendiente", "Cumplida"]
                    new_est = st.selectbox("", opts, index=opts.index(v["estado"]) if v["estado"] in opts else 1,
                                           key=f"vest_{v['id']}", label_visibility="collapsed")
                    if new_est != v["estado"]:
                        db.update_vacacion_estado(v["id"], new_est)
                        st.rerun()
                with c4:
                    if v.get("dias_acum", 0) > 0:
                        st.caption(f'📆 {v["dias_acum"]} días acum.')
                    if venc:
                        st.caption("✔️ Período cumplido")
                with c5:
                    if st.button("🗑️", key=f"dv_{v['id']}"):
                        db.delete_vacacion(v["id"])
                        st.rerun()
                st.divider()

    with tab_acum:
        st.markdown("#### 📆 Días acumulados por operario")
        st.caption("Operarios con ≥15 días acumulados sin fecha programada generan alerta.")
        acum_nombres = {}
        for v in vac_data:
            if v.get("dias_acum", 0) > 0:
                acum_nombres[v["nombre"]] = max(acum_nombres.get(v["nombre"], 0), v["dias_acum"])

        if not acum_nombres:
            empty_state("📆", "No hay datos de días acumulados")
        else:
            rows_a = [
                {"Operario": n, "Días acumulados": d, "Alerta": "⚠️ SÍ" if d >= 15 else "OK"}
                for n, d in sorted(acum_nombres.items(), key=lambda x: -x[1])
            ]
            st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)

    with tab_imp:
        st.markdown("#### 📂 Importar Excel de vacaciones")
        st.info("Columnas mínimas: **Nombre operario** · **Fecha salida** · **Fecha ingreso** · Estado (opcional) · Días acumulados (opcional)")

        file_v = st.file_uploader("Archivo Excel / CSV", type=["xlsx", "xls", "csv"], key="vac_upload")
        if file_v:
            try:
                df_v = pd.read_csv(file_v) if file_v.name.endswith(".csv") else pd.read_excel(file_v)
                st.dataframe(df_v.head(), use_container_width=True)
                cols = df_v.columns.tolist()
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1: col_vn = st.selectbox("👤 Nombre", cols, key="v_cn")
                with c2: col_vs = st.selectbox("📅 Salida (inicio)", cols, key="v_cs")
                with c3: col_vi = st.selectbox("📅 Ingreso (fin)", cols, key="v_ci")
                with c4: col_ve = st.selectbox("Estado", ["— Ninguna —"] + cols, key="v_ce")
                with c5: col_vd = st.selectbox("Días acum.", ["— Ninguna —"] + cols, key="v_cd")

                if st.button("✅ Importar vacaciones", type="primary"):
                    ok, err = 0, 0
                    for _, row_v in df_v.iterrows():
                        try:
                            nombre = str(row_v[col_vn]).strip()
                            salida = pd.to_datetime(row_v[col_vs]).date().isoformat()
                            ingreso = pd.to_datetime(row_v[col_vi]).date().isoformat()
                            estado = str(row_v.get(col_ve, "Pendiente")).strip() if col_ve != "— Ninguna —" else "Pendiente"
                            if estado not in ["Aprobada", "Pendiente", "Cumplida"]:
                                estado = "Pendiente"
                            dias_ac = int(float(row_v.get(col_vd, 0) or 0)) if col_vd != "— Ninguna —" else 0
                            db.create_vacacion(nombre, salida, ingreso, estado, dias_ac)
                            ok += 1
                        except Exception:
                            err += 1
                    st.success(f"✅ {ok} importadas" + (f" · {err} errores" if err else ""))
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        if st.button("🗑️ Limpiar todos los registros", type="secondary"):
            with get_connection() as conn:
                conn.execute("DELETE FROM vacaciones")
            st.success("Registros eliminados")
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  MÓDULO: CUMPLEAÑOS
# ══════════════════════════════════════════════════════════════

def app_cumpleanios():
    section_header("🎂 Gestión de Cumpleaños",
                   "Importa el Excel · 4 horas disponibles el día del cumpleaños",
                   gradient="135deg,#7c3aed,#a855f7")

    cum_data = db.get_all_cumpleanios()
    hoy_list   = cumpleaños_hoy(cum_data)
    prox_list  = cumpleaños_proximos(cum_data, 30)

    # Banner si hay cumpleaños hoy
    if hoy_list:
        nombres_hoy = ", ".join(c["nombre"] for c in hoy_list)
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#f59e0b,#fbbf24);border-radius:12px;
                    padding:14px 18px;margin-bottom:14px;color:#fff">
            <div style="font-weight:800;font-size:1rem">🎉 ¡Cumpleaños hoy!</div>
            <div style="font-size:.9rem;opacity:.95">{nombres_hoy}</div>
        </div>
        """, unsafe_allow_html=True)

    # Estadísticas
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total registros", len(cum_data))
    with c2: st.metric("Cumplen hoy", len(hoy_list))
    with c3: st.metric("Próximos 30d", len(prox_list))
    with c4: st.metric("Horas asignadas", sum(1 for c in cum_data if c.get("asignado")))

    tab_lista, tab_disp, tab_prox, tab_imp = st.tabs(
        ["📋 Todos", "🎁 Disponibles hoy", "📅 Próximos 30 días", "📂 Importar"]
    )

    with tab_lista:
        buscar_cum = st.text_input("🔍", key="src_cum", label_visibility="collapsed", placeholder="🔍 Buscar por nombre...")
        mes_f = st.selectbox("Mes", ["Todos los meses"] + MESES_ES[1:], key="cum_mes")

        cum_f = cum_data
        if buscar_cum:
            cum_f = [c for c in cum_f if buscar_cum.lower() in c["nombre"].lower()]
        if mes_f != "Todos los meses":
            mes_idx = MESES_ES.index(mes_f)
            cum_f = [c for c in cum_f if (parse_fecha_cumpleaños(c["fecha"]) or (0, 0))[0] == mes_idx]

        if not cum_f:
            empty_state("🎂", "No hay registros de cumpleaños")
        else:
            for c in paginate(cum_f, 20, "pag_cum"):
                parsed = parse_fecha_cumpleaños(c["fecha"])
                fecha_str = f"{parsed[1]:02d}/{MESES_ES[parsed[0]]}" if parsed else c["fecha"]

                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                with col1:
                    st.markdown(f'**{c["nombre"]}**')
                with col2:
                    st.caption(f'🎂 {fecha_str}')
                with col3:
                    obs = st.text_input("Obs", value=c.get("observacion",""), key=f"cum_obs_{c['id']}",
                                        label_visibility="collapsed", placeholder="Observación...")
                    if obs != c.get("observacion",""):
                        db.update_cumpleaños_asignado(c["id"], bool(c.get("asignado")), obs)
                with col4:
                    asig = st.checkbox("Horas asignadas", value=bool(c.get("asignado")), key=f"cum_asig_{c['id']}")
                    if asig != bool(c.get("asignado")):
                        db.update_cumpleaños_asignado(c["id"], asig, c.get("observacion",""))
                        st.rerun()
                with col5:
                    if st.button("🗑️", key=f"dc_{c['id']}"):
                        db.delete_cumpleaños(c["id"])
                        st.rerun()
                st.divider()

    with tab_disp:
        st.markdown("#### 🎁 Con horas disponibles hoy")
        disp = [c for c in hoy_list if not c.get("asignado")]
        if not disp:
            empty_state("🎁", "No hay horas de cumpleaños disponibles hoy")
        else:
            for c in disp:
                c1, c2, c3 = st.columns([3, 3, 2])
                with c1: st.markdown(f'🎉 **{c["nombre"]}**')
                with c2: st.caption("4 horas disponibles")
                with c3:
                    if st.button("✅ Marcar asignado", key=f"asig_hoy_{c['id']}"):
                        db.update_cumpleaños_asignado(c["id"], True)
                        st.rerun()
                st.divider()

    with tab_prox:
        st.markdown("#### 📅 Cumpleaños en los próximos 30 días")
        if not prox_list:
            empty_state("📅", "No hay cumpleaños en los próximos 30 días")
        else:
            rows_p = [
                {"Nombre": c["nombre"],
                 "Fecha": c["fecha"],
                 "Faltan (días)": c.get("_dias_faltan",""),
                 "Asignado": "✅" if c.get("asignado") else "Pendiente"}
                for c in prox_list
            ]
            st.dataframe(pd.DataFrame(rows_p), use_container_width=True, hide_index=True)

    with tab_imp:
        st.markdown("#### 📂 Importar Excel de cumpleaños")
        st.info("Columnas mínimas: **Nombre** · **Fecha de cumpleaños** (DD/MM/AAAA o AAAA-MM-DD)")

        file_cum = st.file_uploader("Archivo Excel / CSV", type=["xlsx", "xls", "csv"], key="cum_upload")
        if file_cum:
            try:
                df_cum = pd.read_csv(file_cum) if file_cum.name.endswith(".csv") else pd.read_excel(file_cum, dtype=str)
                st.dataframe(df_cum.head(), use_container_width=True)
                cols_c = df_cum.columns.tolist()
                c1, c2 = st.columns(2)
                with c1: col_cn = st.selectbox("👤 Nombre", cols_c, key="cum_cn")
                with c2: col_cf = st.selectbox("🎂 Fecha", cols_c, key="cum_cf")

                if st.button("🎉 Importar", type="primary"):
                    ok = 0
                    for _, row_c in df_cum.iterrows():
                        nombre = str(row_c.get(col_cn, "")).strip()
                        fecha  = str(row_c.get(col_cf, "")).strip()
                        if nombre and fecha:
                            db.create_cumpleaños(nombre, fecha)
                            ok += 1
                    st.success(f"✅ {ok} registros importados")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Agregar manualmente**")
            with st.form("form_cum_manual", clear_on_submit=True):
                nom_m = st.text_input("👤 Nombre")
                fec_m = st.date_input("🎂 Fecha de cumpleaños")
                if st.form_submit_button("+ Agregar"):
                    if nom_m.strip():
                        db.create_cumpleaños(nom_m, fec_m.strftime("%d/%m/%Y"))
                        st.success(f"✅ {nom_m} agregado")
                        st.rerun()
        with c2:
            if st.button("🗑️ Limpiar todos", type="secondary"):
                db.delete_all_cumpleanios()
                st.rerun()


# ══════════════════════════════════════════════════════════════
#  MÓDULO: CENTRO DE COSTOS
# ══════════════════════════════════════════════════════════════

def app_centro_costos():
    section_header("💰 Centro de Costos",
                   "CC Inscrito = nómina · CC Actual = donde trabaja ahora",
                   gradient="135deg,#064e3b,#059669")

    workers = db.get_all_workers()
    cc_all  = db.get_all_cc()
    cc_map  = {c["worker_id"]: c for c in cc_all}

    # Estadísticas
    total_w  = len(workers)
    con_cc   = sum(1 for w in workers if cc_map.get(w["id"], {}).get("inscrito"))
    sin_cc   = total_w - con_cc
    diferente = sum(
        1 for w in workers
        if (cc := cc_map.get(w["id"]))
        and cc.get("inscrito") and cc.get("actual")
        and cc["actual"] != cc["inscrito"]
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total operarios", total_w)
    with c2: st.metric("Con CC inscrito", con_cc)
    with c3: st.metric("CC diferente", diferente)
    with c4: st.metric("Sin CC inscrito", sin_cc)

    tab_lista, tab_sin, tab_imp = st.tabs(["👥 Operarios", "⚠️ Sin asignar", "📂 Importar / Manual"])

    with tab_lista:
        c1, c2 = st.columns([3, 1])
        with c1:
            buscar_cc = st.text_input("🔍", key="src_cc", label_visibility="collapsed", placeholder="🔍 Buscar por nombre, CC o grupo...")
        with c2:
            f_cc_est = st.selectbox("Estado", ["Todos", "Coincide", "Diferente", "Sin CC"], key="fcc_est", label_visibility="collapsed")

        workers_f = [
            w for w in workers
            if not buscar_cc or buscar_cc.lower() in (w["nombre"] + w["grupo"]).lower()
        ]

        if not workers_f:
            empty_state()
        else:
            for w in workers_f:
                cc = cc_map.get(w["id"], {"inscrito": "", "actual": ""})
                ins = cc.get("inscrito", "")
                act = cc.get("actual", "") or ins
                estado_cc = "Sin CC" if not ins else ("Diferente" if act and act != ins else "Coincide")

                if f_cc_est != "Todos" and estado_cc != f_cc_est:
                    continue

                c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 2, 1])
                with c1:
                    st.markdown(f'**{w["nombre"]}** {badge_grupo(w["grupo"])}', unsafe_allow_html=True)
                with c2:
                    st.caption(w.get("maquina") or "—")
                with c3:
                    new_ins = st.text_input("CC Inscrito", value=ins, key=f"cc_ins_{w['id']}",
                                            label_visibility="collapsed", placeholder="CC Inscrito")
                with c4:
                    new_act = st.text_input("CC Actual", value=act, key=f"cc_act_{w['id']}",
                                            label_visibility="collapsed", placeholder="CC Actual")
                with c5:
                    if st.button("💾", key=f"save_cc_{w['id']}", help="Guardar CC"):
                        db.upsert_cc(w["id"], new_ins, new_act)
                        st.rerun()
                st.divider()

    with tab_sin:
        sin_lista = [w for w in workers if not cc_map.get(w["id"], {}).get("inscrito")]
        if not sin_lista:
            st.success("✅ Todos los operarios tienen CC inscrito")
        else:
            st.warning(f"⚠️ {len(sin_lista)} operarios sin CC inscrito")
            for w in sin_lista:
                st.markdown(f'- **{w["nombre"]}** · Grupo {w["grupo"]}')

    with tab_imp:
        st.markdown("#### ✍️ Asignación manual")
        with st.form("form_cc_manual", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                w_opts_cc = {f"{w['nombre']} (G{w['grupo']})": w["id"] for w in workers}
                w_sel_cc = st.selectbox("👤 Operario", list(w_opts_cc.keys()))
            with c2:
                cc_ins_m = st.text_input("💰 CC Inscrito *")
            with c3:
                cc_act_m = st.text_input("📍 CC Actual (si difiere)")
            if st.form_submit_button("+ Guardar", type="primary"):
                if cc_ins_m.strip():
                    db.upsert_cc(w_opts_cc[w_sel_cc], cc_ins_m, cc_act_m)
                    st.success("✅ Guardado")
                    st.rerun()

        st.divider()
        st.markdown("#### 📂 Importar desde archivo")
        st.info("Columnas mínimas: **Nombre** · **CC Inscrito** · CC Actual (opcional)")
        file_cc = st.file_uploader("Archivo Excel / CSV", type=["xlsx", "xls", "csv"], key="cc_upload")
        if file_cc:
            try:
                df_cc = pd.read_csv(file_cc) if file_cc.name.endswith(".csv") else pd.read_excel(file_cc, dtype=str)
                st.dataframe(df_cc.head(), use_container_width=True)
                cols_cc = df_cc.columns.tolist()
                c1, c2, c3 = st.columns(3)
                with c1: col_ccn = st.selectbox("👤 Nombre", cols_cc, key="ccn")
                with c2: col_cci = st.selectbox("💰 CC Inscrito", cols_cc, key="cci")
                with c3: col_cca = st.selectbox("📍 CC Actual", ["— Igual al inscrito —"] + cols_cc, key="cca")

                if st.button("✅ Importar CC", type="primary"):
                    ok, no_enc = 0, 0
                    for _, row_cc in df_cc.iterrows():
                        nom = str(row_cc.get(col_ccn, "")).strip()
                        ins = str(row_cc.get(col_cci, "")).strip()
                        act = str(row_cc.get(col_cca, "")).strip() if col_cca != "— Igual al inscrito —" else ""
                        w_m = next((x for x in workers if norm_nombre(x["nombre"]) == norm_nombre(nom)), None)
                        if w_m and ins:
                            db.upsert_cc(w_m["id"], ins, act)
                            ok += 1
                        elif nom:
                            no_enc += 1
                    msg = f"✅ {ok} actualizados"
                    if no_enc:
                        msg += f" · {no_enc} nombres no encontrados"
                    st.success(msg)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        # Exportar Excel
        st.divider()
        if st.button("⬇️ Exportar a Excel", type="secondary"):
            monday = get_monday()
            rot_w = get_rot_week(monday)
            rows_exp = []
            for i, w in enumerate(workers):
                t = get_turno(w["grupo"], rot_w)
                cc = cc_map.get(w["id"], {"inscrito": "", "actual": ""})
                ins = cc.get("inscrito", "")
                act = cc.get("actual", "") or ins
                est = "Sin CC" if not ins else ("Diferente" if act and act != ins else "Coincide")
                rows_exp.append({
                    "#": i + 1,
                    "Nombre": w["nombre"],
                    "Grupo": f"Grupo {w['grupo']}",
                    "Turno": t["nombre"],
                    "Máquina": w.get("maquina") or "",
                    "CC Inscrito": ins,
                    "CC Actual": act,
                    "Estado": est,
                })
            buf = io.BytesIO()
            pd.DataFrame(rows_exp).to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                "⬇️ Descargar Excel",
                data=buf,
                file_name=f"centro_costos_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ══════════════════════════════════════════════════════════════
#  MAIN — ROUTER
# ══════════════════════════════════════════════════════════════

def main():
    # Verificar sesión
    if not st.session_state.get("logged_in"):
        login_page()
        return

    # Sidebar de navegación
    with st.sidebar:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1E3A8A,#3B82F6);border-radius:10px;
                    padding:14px;text-align:center;margin-bottom:16px;color:#fff">
            <div style="font-size:1.8rem">🏭</div>
            <div style="font-weight:800;font-size:.95rem">Sistema de Turnos</div>
            <div style="font-size:.72rem;opacity:.8">v3.0 · SQLite</div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"👤 **{st.session_state.get('usuario', '')}** · {st.session_state.get('rol', '')}")

        st.markdown("---")
        modulo = st.radio(
            "Módulo",
            ["🏭 Turnos", "🔄 Compensatorios", "🌴 Vacaciones", "🎂 Cumpleaños", "💰 Centro de Costos"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            for k in ["logged_in", "usuario", "rol", "week_offset"]:
                st.session_state.pop(k, None)
            st.rerun()

        st.caption("💡 Los datos se guardan automáticamente en SQLite.")

    # Enrutar al módulo seleccionado
    if "Turnos" in modulo:
        app_turnos()
    elif "Compensatorios" in modulo:
        app_compensatorios()
    elif "Vacaciones" in modulo:
        app_vacaciones()
    elif "Cumpleaños" in modulo:
        app_cumpleanios()
    elif "Centro de Costos" in modulo:
        app_centro_costos()


# Import necesario para limpiar vacaciones
from contextlib import contextmanager
from database.db import get_connection

if __name__ == "__main__":
    main()
else:
    main()
