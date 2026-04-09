"""
database/db.py
Capa de acceso a datos. Usa SQLite por defecto.
Para migrar a PostgreSQL: reemplaza get_connection() con psycopg2 / SQLAlchemy.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "db.sqlite3")


@contextmanager
def get_connection():
    """Contexto de conexión. Cambia aquí para usar PostgreSQL."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Inicialización de tablas ───────────────────────────────────
def init_db():
    """Crea todas las tablas si no existen."""
    with get_connection() as conn:
        conn.executescript("""
        -- Trabajadores
        CREATE TABLE IF NOT EXISTS workers (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL,
            grupo     TEXT    NOT NULL CHECK(grupo IN ('A','B','C')),
            maquina   TEXT    DEFAULT ''
        );

        -- Ausencias
        CREATE TABLE IF NOT EXISTS ausencias (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id    INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            tipo         TEXT    NOT NULL,
            fecha_inicio TEXT    NOT NULL,
            fecha_fin    TEXT    NOT NULL,
            estado       TEXT    NOT NULL DEFAULT 'Pendiente',
            observacion  TEXT    DEFAULT ''
        );

        -- Horas extras: almacenado como JSON por semana por trabajador
        CREATE TABLE IF NOT EXISTS horas_extras (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            semana    TEXT    NOT NULL,   -- ISO week start YYYY-MM-DD
            datos     TEXT    NOT NULL DEFAULT '{}',  -- JSON {ED:0, EN:0, ...}
            UNIQUE(worker_id, semana)
        );

        -- Celdas de estado (turno manual override por día y trabajador)
        CREATE TABLE IF NOT EXISTS celdas_estado (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            clave     TEXT    NOT NULL UNIQUE,   -- "wId-YYYY-MM-DD"
            valor     TEXT    NOT NULL DEFAULT ''
        );

        -- Vacaciones (períodos)
        CREATE TABLE IF NOT EXISTS vacaciones (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL,
            salida    TEXT    NOT NULL,   -- YYYY-MM-DD
            ingreso   TEXT    NOT NULL,   -- YYYY-MM-DD
            estado    TEXT    NOT NULL DEFAULT 'Pendiente',
            dias_acum INTEGER DEFAULT 0
        );

        -- Cumpleaños
        CREATE TABLE IF NOT EXISTS cumpleanios (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL UNIQUE,
            fecha     TEXT    NOT NULL,   -- MM-DD (ignorar año) o YYYY-MM-DD
            asignado  INTEGER DEFAULT 0,  -- 1 = horas cumpleaños ya asignadas
            observacion TEXT  DEFAULT ''
        );

        -- Centro de costos
        CREATE TABLE IF NOT EXISTS centro_costos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id  INTEGER NOT NULL UNIQUE REFERENCES workers(id) ON DELETE CASCADE,
            inscrito   TEXT    DEFAULT '',
            actual     TEXT    DEFAULT ''
        );

        -- Compensatorios ganados (horas compensatorias disponibles por nombre)
        CREATE TABLE IF NOT EXISTS comp_ganados (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL UNIQUE,
            horas     REAL    NOT NULL DEFAULT 0
        );

        -- Usuarios del sistema (login)
        CREATE TABLE IF NOT EXISTS usuarios (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT    NOT NULL UNIQUE,
            password  TEXT    NOT NULL,
            rol       TEXT    NOT NULL DEFAULT 'admin'
        );
        """)

        # Datos iniciales
        _seed_initial_data(conn)


def _seed_initial_data(conn):
    """Inserta datos de ejemplo si las tablas están vacías."""
    # Usuarios por defecto
    count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )
        conn.execute(
            "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
            ("super", "super123", "superadmin")
        )

    # Trabajadores de ejemplo
    count = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    if count == 0:
        sample_workers = [
            ("Juan Pérez",   "A", ""),
            ("María López",  "B", ""),
            ("Carlos Gómez", "C", ""),
            ("Ana Torres",   "A", ""),
            ("Luis Ramírez", "B", ""),
        ]
        conn.executemany(
            "INSERT INTO workers (nombre, grupo, maquina) VALUES (?, ?, ?)",
            sample_workers
        )


# ══════════════════════════════════════════════════════════════
#  WORKERS CRUD
# ══════════════════════════════════════════════════════════════

def get_all_workers():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM workers ORDER BY grupo, nombre"
        ).fetchall()]


def get_worker(worker_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        return dict(row) if row else None


def create_worker(nombre: str, grupo: str, maquina: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO workers (nombre, grupo, maquina) VALUES (?, ?, ?)",
            (nombre.strip(), grupo, maquina.strip())
        )
        return cur.lastrowid


def update_worker(worker_id: int, nombre: str, grupo: str, maquina: str = ""):
    with get_connection() as conn:
        conn.execute(
            "UPDATE workers SET nombre=?, grupo=?, maquina=? WHERE id=?",
            (nombre.strip(), grupo, maquina.strip(), worker_id)
        )


def delete_worker(worker_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM workers WHERE id=?", (worker_id,))


# ══════════════════════════════════════════════════════════════
#  AUSENCIAS CRUD
# ══════════════════════════════════════════════════════════════

def get_all_ausencias():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT a.*, w.nombre as worker_nombre, w.grupo as worker_grupo
            FROM ausencias a
            JOIN workers w ON w.id = a.worker_id
            ORDER BY a.fecha_inicio DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_ausencias_by_worker(worker_id: int):
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ausencias WHERE worker_id=? ORDER BY fecha_inicio DESC",
            (worker_id,)
        ).fetchall()]


def create_ausencia(worker_id: int, tipo: str, fecha_inicio: str,
                    fecha_fin: str, estado: str = "Pendiente",
                    observacion: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO ausencias
               (worker_id, tipo, fecha_inicio, fecha_fin, estado, observacion)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (worker_id, tipo, fecha_inicio, fecha_fin, estado, observacion)
        )
        return cur.lastrowid


def update_ausencia(aus_id: int, tipo: str, fecha_inicio: str,
                    fecha_fin: str, estado: str, observacion: str = ""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE ausencias
               SET tipo=?, fecha_inicio=?, fecha_fin=?, estado=?, observacion=?
               WHERE id=?""",
            (tipo, fecha_inicio, fecha_fin, estado, observacion, aus_id)
        )


def update_ausencia_estado(aus_id: int, estado: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE ausencias SET estado=? WHERE id=?",
            (estado, aus_id)
        )


def delete_ausencia(aus_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM ausencias WHERE id=?", (aus_id,))


# ══════════════════════════════════════════════════════════════
#  HORAS EXTRAS CRUD
# ══════════════════════════════════════════════════════════════

def get_horas_extras(worker_id: int, semana: str) -> dict:
    """Retorna dict de tipos HE para un trabajador en una semana."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT datos FROM horas_extras WHERE worker_id=? AND semana=?",
            (worker_id, semana)
        ).fetchone()
        if row:
            return json.loads(row["datos"])
        return {"ED": 0, "EN": 0, "RN": 0, "DOM": 0, "DOMN": 0, "EDD": 0, "END": 0}


def set_horas_extras(worker_id: int, semana: str, datos: dict):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO horas_extras (worker_id, semana, datos)
               VALUES (?, ?, ?)
               ON CONFLICT(worker_id, semana) DO UPDATE SET datos=excluded.datos""",
            (worker_id, semana, json.dumps(datos))
        )


def get_all_horas_extras_semana(semana: str) -> list:
    """Todas las HE de todos los trabajadores en una semana."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT he.*, w.nombre, w.grupo
            FROM horas_extras he
            JOIN workers w ON w.id = he.worker_id
            WHERE he.semana = ?
        """, (semana,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["datos"] = json.loads(d["datos"])
            result.append(d)
        return result


# ══════════════════════════════════════════════════════════════
#  CELDAS ESTADO
# ══════════════════════════════════════════════════════════════

def get_celda_estado(clave: str) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT valor FROM celdas_estado WHERE clave=?", (clave,)
        ).fetchone()
        return row["valor"] if row else ""


def set_celda_estado(clave: str, valor: str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO celdas_estado (clave, valor) VALUES (?, ?)
               ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor""",
            (clave, valor)
        )


# ══════════════════════════════════════════════════════════════
#  VACACIONES CRUD
# ══════════════════════════════════════════════════════════════

def get_all_vacaciones():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM vacaciones ORDER BY salida DESC"
        ).fetchall()]


def create_vacacion(nombre: str, salida: str, ingreso: str,
                    estado: str = "Pendiente", dias_acum: int = 0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO vacaciones (nombre, salida, ingreso, estado, dias_acum) VALUES (?,?,?,?,?)",
            (nombre.strip(), salida, ingreso, estado, dias_acum)
        )
        return cur.lastrowid


def update_vacacion_estado(vac_id: int, estado: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE vacaciones SET estado=? WHERE id=?", (estado, vac_id)
        )


def delete_vacacion(vac_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM vacaciones WHERE id=?", (vac_id,))


def update_vacacion_acum(nombre: str, dias: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE vacaciones SET dias_acum=? WHERE nombre=?", (dias, nombre)
        )


# ══════════════════════════════════════════════════════════════
#  CUMPLEAÑOS CRUD
# ══════════════════════════════════════════════════════════════

def get_all_cumpleanios():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cumpleanios ORDER BY nombre"
        ).fetchall()]


def create_cumpleaños(nombre: str, fecha: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO cumpleanios (nombre, fecha) VALUES (?, ?)",
            (nombre.strip(), fecha)
        )
        return cur.lastrowid


def update_cumpleaños_asignado(cum_id: int, asignado: bool, observacion: str = ""):
    with get_connection() as conn:
        conn.execute(
            "UPDATE cumpleanios SET asignado=?, observacion=? WHERE id=?",
            (1 if asignado else 0, observacion, cum_id)
        )


def delete_cumpleaños(cum_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM cumpleanios WHERE id=?", (cum_id,))


def delete_all_cumpleanios():
    with get_connection() as conn:
        conn.execute("DELETE FROM cumpleanios")


# ══════════════════════════════════════════════════════════════
#  CENTRO DE COSTOS CRUD
# ══════════════════════════════════════════════════════════════

def get_all_cc():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT cc.*, w.nombre, w.grupo, w.maquina
            FROM centro_costos cc
            JOIN workers w ON w.id = cc.worker_id
            ORDER BY w.nombre
        """).fetchall()
        return [dict(r) for r in rows]


def upsert_cc(worker_id: int, inscrito: str, actual: str = ""):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO centro_costos (worker_id, inscrito, actual) VALUES (?, ?, ?)
               ON CONFLICT(worker_id) DO UPDATE SET inscrito=excluded.inscrito, actual=excluded.actual""",
            (worker_id, inscrito.strip(), actual.strip())
        )


def get_cc_by_worker(worker_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM centro_costos WHERE worker_id=?", (worker_id,)
        ).fetchone()
        return dict(row) if row else {"inscrito": "", "actual": ""}


# ══════════════════════════════════════════════════════════════
#  COMPENSATORIOS
# ══════════════════════════════════════════════════════════════

def get_all_comp_ganados():
    with get_connection() as conn:
        return {r["nombre"]: r["horas"] for r in conn.execute(
            "SELECT * FROM comp_ganados"
        ).fetchall()}


def set_comp_ganados(nombre: str, horas: float):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO comp_ganados (nombre, horas) VALUES (?, ?)
               ON CONFLICT(nombre) DO UPDATE SET horas=excluded.horas""",
            (nombre, horas)
        )


# ══════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════

def verificar_usuario(username: str, password: str):
    """Retorna el usuario si las credenciales son válidas, None si no."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username=? AND password=?",
            (username.strip().lower(), password)
        ).fetchone()
        return dict(row) if row else None
