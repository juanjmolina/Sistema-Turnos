"""
modules/logic.py
Lógica de negocio: rotación de turnos, cálculo de HE, compensatorios.
Sin dependencias de UI — puro Python.
"""
from datetime import date, timedelta
from typing import Optional
import unicodedata

# ── Constantes del negocio ─────────────────────────────────────

TURNOS = [
    {"id": 0, "nombre": "Mañana", "horario": "6:00-14:00",  "color": "#F59E0B", "bg": "#FEF3C7", "text": "#92400E"},
    {"id": 1, "nombre": "Tarde",  "horario": "14:00-22:00", "color": "#3B82F6", "bg": "#DBEAFE", "text": "#1E3A8A"},
    {"id": 2, "nombre": "Noche",  "horario": "22:00-6:00",  "color": "#8B5CF6", "bg": "#EDE9FE", "text": "#4C1D95"},
]
GRUPOS = ["A", "B", "C"]
DIAS   = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# Ancla de rotación: 30-mar-2026 → Grupo A=Noche, B=Mañana, C=Tarde
ANCLA = date(2026, 3, 30)

TIPOS_HE = [
    {"id": "ED",   "label": "Extra Diurna",                    "recargo": 25,  "color": "#F59E0B", "bg": "#FEF3C7", "icon": "☀️"},
    {"id": "EN",   "label": "Extra Nocturna",                  "recargo": 75,  "color": "#8B5CF6", "bg": "#EDE9FE", "icon": "🌙"},
    {"id": "RN",   "label": "Recargo Nocturno",                "recargo": 35,  "color": "#6366F1", "bg": "#E0E7FF", "icon": "🌃"},
    {"id": "DOM",  "label": "Dominical/Festivo Diurno",        "recargo": 80,  "color": "#10B981", "bg": "#D1FAE5", "icon": "📅"},
    {"id": "DOMN", "label": "Dominical/Festivo Nocturno",      "recargo": 110, "color": "#EC4899", "bg": "#FCE7F3", "icon": "🌙📅"},
    {"id": "EDD",  "label": "Extra Diurna en Dominical",       "recargo": 100, "color": "#EF4444", "bg": "#FEE2E2", "icon": "☀️📅"},
    {"id": "END",  "label": "Extra Nocturna en Dominical",     "recargo": 150, "color": "#DC2626", "bg": "#FEE2E2", "icon": "🌙🔥"},
]
HE_IDS = [t["id"] for t in TIPOS_HE]

LIMITE_DIARIO  = 2
LIMITE_SEMANAL = 12

TIPOS_AUS = [
    {"id": "VIA",  "label": "Viaje",                          "color": "#0EA5E9", "bg": "#E0F2FE", "icon": "✈️"},
    {"id": "IEC",  "label": "Incap. Enfermedad Común",        "color": "#EF4444", "bg": "#FEE2E2", "icon": "🤒"},
    {"id": "VAC",  "label": "Vacaciones",                     "color": "#06B6D4", "bg": "#CFFAFE", "icon": "🌴"},
    {"id": "MAT",  "label": "Lic. Maternidad/Paternidad",     "color": "#EC4899", "bg": "#FCE7F3", "icon": "👶"},
    {"id": "CAL",  "label": "Calamidad Doméstica",            "color": "#7C3AED", "bg": "#EDE9FE", "icon": "🏠"},
    {"id": "TPC",  "label": "Trabajo/Capacitación por fuera", "color": "#F59E0B", "bg": "#FEF3C7", "icon": "🏢"},
    {"id": "IAL",  "label": "Incap. Accidente Laboral",       "color": "#DC2626", "bg": "#FEE2E2", "icon": "🦺"},
    {"id": "SUS",  "label": "Suspensión",                     "color": "#64748B", "bg": "#F1F5F9", "icon": "🚫"},
    {"id": "IEL",  "label": "Incap. Enfermedad Laboral",      "color": "#9333EA", "bg": "#F3E8FF", "icon": "⚕️"},
    {"id": "AR",   "label": "Ausencia Remunerada",            "color": "#10B981", "bg": "#D1FAE5", "icon": "✅"},
    {"id": "ANR",  "label": "Ausencia No Remunerada",         "color": "#F97316", "bg": "#FFF7ED", "icon": "🟠"},
    {"id": "MAR",  "label": "Matrimonio",                     "color": "#E11D48", "bg": "#FFE4E6", "icon": "💍"},
    {"id": "GRA",  "label": "Grados",                         "color": "#8B5CF6", "bg": "#EDE9FE", "icon": "🎓"},
    {"id": "CHE",  "label": "Compensatorio por Horas Extras", "color": "#0369A1", "bg": "#E0F2FE", "icon": "🔄"},
]
TIPOS_AUS_MAP = {t["id"]: t for t in TIPOS_AUS}

ESTADOS_AUS = ["Pendiente", "Aprobado", "Rechazado"]

MAQUINAS_LIST = [
    "Delta 1","Alpha 1","Alpha 2","Alpha 3","Alpha 4",
    "Omicron 2","Omicron 3","Omicron 4","Omicron 5","Omicron 6",
    "Kappa 2","Despachos","Omega 1","Omega 2","Omega 3","Omega 4",
    "Omega 7","Omega 9","Omega 5 prati","Laminación flexible",
    "Patinador","Marcación Ink Jet","Lambda","Sleeves 2","Alistamiento",
    "Clises - Mallas","Tintas","Hp índigo","PHI","Almacen",
    "Líder de entregas","Supervisores","Inspector","Of. producción",
    "Ptari - Of. varios","Of. varios","Centro de excelencia","Calidad",
]

MESES_ES = [
    "", "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
]


# ── Rotación de turnos ─────────────────────────────────────────

def get_monday(week_offset: int = 0) -> date:
    """Lunes de la semana actual ± offset."""
    today = date.today()
    diff = today.weekday()          # 0=Lun … 6=Dom
    monday = today - timedelta(days=diff)
    return monday + timedelta(weeks=week_offset)


def get_rot_week(monday: date) -> int:
    """Semanas enteras desde el ancla."""
    return round((monday - ANCLA).days / 7)


def get_turno(grupo: str, rot_week: int) -> dict:
    """Turno base del grupo para la semana."""
    paso = (rot_week if rot_week >= 0 else rot_week + 600) // 2
    # +2 → ancla 30-mar-2026: A=Noche, B=Mañana, C=Tarde
    idx = (GRUPOS.index(grupo) + paso % 3 + 2 + 300) % 3
    return TURNOS[idx]


def get_turno_info(turno_base: dict, d_idx: int) -> dict:
    """Ajusta horario para sábado/domingo."""
    tid = turno_base["id"]
    if d_idx == 4 and tid == 2:     # Viernes Noche
        return {**turno_base, "nombre": "Noche", "horario": "22:00 → Sáb 5:00", "descanso": False}
    if d_idx == 5:                  # Sábado
        if tid == 0:
            return {**turno_base, "nombre": "Mañana", "horario": "5:00 → 11:00", "descanso": False}
        if tid == 1:
            return {**turno_base, "nombre": "Tarde",  "horario": "11:00 → 17:00", "descanso": False}
        if tid == 2:
            return {**turno_base, "nombre": "Descanso", "horario": "desde 17:00",
                    "bg": "#F1F5F9", "text": "#94A3B8", "descanso": True}
    if d_idx == 6:                  # Domingo
        if tid == 2:
            return {**turno_base, "nombre": "Noche", "horario": "23:00 → Lun 6:00", "descanso": False}
        return {**turno_base, "nombre": "Descanso", "horario": "", "bg": "#F1F5F9", "text": "#94A3B8", "descanso": True}
    return {**turno_base, "descanso": False}


def get_week_dates(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(7)]


def week_label(week_offset: int) -> str:
    mapping = {0: "Semana actual", 1: "Próxima semana", -1: "Semana anterior"}
    if week_offset in mapping:
        return mapping[week_offset]
    return f"+{week_offset} semanas" if week_offset > 0 else f"{week_offset} semanas"


def get_periodo_info(week_offset: int) -> dict:
    """Info del período de 15 días actual."""
    monday = get_monday(week_offset)
    rw = get_rot_week(monday)
    es_s1 = (rw % 2 == 0)
    dias_en_periodo = ((rw % 2) + 2) % 2
    dias_para_cambio = (2 - dias_en_periodo) * 7
    return {
        "rot_week": rw,
        "es_primera": es_s1,
        "label_semana": "1ª semana del período" if es_s1 else "2ª semana del período",
        "dias_para_cambio": dias_para_cambio,
    }


# ── Horas extras ───────────────────────────────────────────────

def total_he_worker(he: dict) -> float:
    return sum(he.get(t, 0) for t in HE_IDS)


def empty_he() -> dict:
    return {t: 0 for t in HE_IDS}


# ── Ausencias ──────────────────────────────────────────────────

def days_between(a: str, b: str) -> int:
    """Días calendario entre dos fechas ISO (inclusive)."""
    d1 = date.fromisoformat(a)
    d2 = date.fromisoformat(b)
    return abs((d2 - d1).days) + 1


def worker_is_absent(ausencias: list, worker_id: int, target_date: date) -> Optional[dict]:
    """Retorna la ausencia si el trabajador está ausente en la fecha dada."""
    ds = target_date.isoformat()
    for a in ausencias:
        if a["worker_id"] == worker_id and a["estado"] != "Rechazado":
            if a["fecha_inicio"] <= ds <= a["fecha_fin"]:
                return a
    return None


def ausencias_en_semana(ausencias: list, worker_id: int, monday: date) -> list:
    """Ausencias del trabajador que solapan con la semana."""
    week_end = (monday + timedelta(days=6)).isoformat()
    monday_s = monday.isoformat()
    return [
        a for a in ausencias
        if a["worker_id"] == worker_id
        and a["fecha_inicio"] <= week_end
        and a["fecha_fin"] >= monday_s
        and a["estado"] != "Rechazado"
    ]


# ── Compensatorios ─────────────────────────────────────────────

def calcular_comp_disponibles(ausencias: list, workers: list) -> dict:
    """
    Calcula días CHE usados por trabajador a partir de las ausencias tipo CHE aprobadas.
    Retorna {nombre: dias_usados}.
    """
    usados: dict = {}
    for a in ausencias:
        if a["tipo"] != "CHE":
            continue
        w = next((x for x in workers if x["id"] == a["worker_id"]), None)
        if not w:
            continue
        dias = days_between(a["fecha_inicio"], a["fecha_fin"])
        if a["estado"] == "Aprobado":
            usados[w["nombre"]] = usados.get(w["nombre"], 0) + dias
    return usados


# ── Cumpleaños ─────────────────────────────────────────────────

def parse_fecha_cumpleaños(fecha_str: str) -> Optional[tuple[int, int]]:
    """
    Parsea varios formatos de fecha y retorna (mes, dia).
    Acepta: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, MM-DD.
    """
    s = str(fecha_str).strip()
    # Excel serial
    if s.isdigit():
        n = int(s)
        if n > 1000:
            from datetime import datetime
            base = datetime(1899, 12, 30)
            dt = base + timedelta(days=n)
            return dt.month, dt.day
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m-%d", "%d/%m/%y"]:
        try:
            from datetime import datetime
            dt = datetime.strptime(s, fmt)
            return dt.month, dt.day
        except ValueError:
            pass
    return None


def cumpleaños_hoy(cum_data: list) -> list:
    today = date.today()
    result = []
    for c in cum_data:
        parsed = parse_fecha_cumpleaños(c["fecha"])
        if parsed and parsed == (today.month, today.day):
            result.append(c)
    return result


def cumpleaños_proximos(cum_data: list, dias: int = 30) -> list:
    today = date.today()
    result = []
    for c in cum_data:
        parsed = parse_fecha_cumpleaños(c["fecha"])
        if not parsed:
            continue
        mes, dia = parsed
        try:
            this_year = date(today.year, mes, dia)
        except ValueError:
            continue
        if this_year < today:
            try:
                this_year = date(today.year + 1, mes, dia)
            except ValueError:
                continue
        delta = (this_year - today).days
        if 0 < delta <= dias:
            result.append({**c, "_dias_faltan": delta})
    result.sort(key=lambda x: x["_dias_faltan"])
    return result


# ── Vacaciones ─────────────────────────────────────────────────

def vacacion_vencida(vac: dict) -> bool:
    """True si la fecha de ingreso ya pasó."""
    try:
        return date.fromisoformat(vac["ingreso"]) < date.today()
    except Exception:
        return False


def dias_vacacion(vac: dict) -> int:
    try:
        return days_between(vac["salida"], vac["ingreso"])
    except Exception:
        return 0


# ── Utilidades de texto ────────────────────────────────────────

def norm_nombre(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace("  ", " ")


def fmt_date_es(d: date) -> str:
    """Ej: '07 abr'"""
    meses = ["", "ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    return f"{d.day:02d} {meses[d.month]}"


def fmt_full_es(iso: str) -> str:
    """YYYY-MM-DD → '07 abr. 2026'"""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
        meses = ["", "ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
        return f"{d.day:02d} {meses[d.month]}. {d.year}"
    except Exception:
        return iso
