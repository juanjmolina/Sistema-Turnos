"""
database/db.py — Capa de acceso a datos.
SQLite por defecto. Cambia get_connection() para PostgreSQL.
"""
import os, json, sqlite3, hashlib
from datetime import datetime
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db.sqlite3")

def get_connection():
    if DATABASE_URL:
        try:
            import psycopg2
            url = DATABASE_URL.replace("postgres://","postgresql://",1)
            return psycopg2.connect(url), "pg"
        except ImportError:
            raise RuntimeError("Instala psycopg2-binary para PostgreSQL")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def _p(engine): return "%s" if engine=="pg" else "?"

def init_db() -> bool:
    try:
        conn, engine = get_connection()
        cur = conn.cursor()
        if engine == "sqlite":
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clave TEXT NOT NULL UNIQUE,
                    datos TEXT NOT NULL,
                    hash_datos TEXT,
                    creado_en TEXT DEFAULT (datetime('now')),
                    actualizado_en TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT, accion TEXT,
                    creado_en TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_clave ON snapshots(clave);
            """)
        else:
            for sql in [
                """CREATE TABLE IF NOT EXISTS snapshots (
                    id SERIAL PRIMARY KEY, clave TEXT NOT NULL UNIQUE,
                    datos JSONB NOT NULL, hash_datos TEXT,
                    creado_en TIMESTAMPTZ DEFAULT NOW(),
                    actualizado_en TIMESTAMPTZ DEFAULT NOW())""",
                """CREATE TABLE IF NOT EXISTS sync_log (
                    id SERIAL PRIMARY KEY, usuario TEXT, accion TEXT,
                    creado_en TIMESTAMPTZ DEFAULT NOW())""",
                "CREATE INDEX IF NOT EXISTS idx_clave ON snapshots(clave)"
            ]:
                cur.execute(sql)
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[DB] init_db error: {e}"); return False

def guardar_snapshot(clave: str, datos: dict, usuario: str = "sistema") -> bool:
    try:
        conn, engine = get_connection()
        cur = conn.cursor()
        p = _p(engine)
        js = json.dumps(datos, ensure_ascii=False)
        h  = hashlib.md5(js.encode()).hexdigest()
        ts = datetime.utcnow().isoformat()
        if engine == "sqlite":
            cur.execute("""
                INSERT INTO snapshots (clave,datos,hash_datos,creado_en,actualizado_en)
                VALUES (?,?,?,?,?)
                ON CONFLICT(clave) DO UPDATE SET
                  datos=excluded.datos, hash_datos=excluded.hash_datos,
                  actualizado_en=excluded.actualizado_en
            """, (clave, js, h, ts, ts))
        else:
            cur.execute(f"""
                INSERT INTO snapshots (clave,datos,hash_datos,actualizado_en)
                VALUES ({p},{p}::jsonb,{p},NOW())
                ON CONFLICT(clave) DO UPDATE SET
                  datos=EXCLUDED.datos, hash_datos=EXCLUDED.hash_datos,
                  actualizado_en=NOW()
            """, (clave, js, h))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[DB] guardar error: {e}"); return False

def cargar_snapshot(clave: str) -> Optional[dict]:
    try:
        conn, engine = get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT datos,hash_datos,actualizado_en FROM snapshots WHERE clave={_p(engine)}", (clave,))
        row = cur.fetchone(); conn.close()
        if not row: return None
        raw = row[0] if engine=="pg" else row["datos"]
        datos = raw if isinstance(raw, dict) else json.loads(raw)
        return {"datos": datos, "hash": row[1] if engine=="pg" else row["hash_datos"],
                "actualizado_en": str(row[2] if engine=="pg" else row["actualizado_en"])}
    except Exception as e:
        print(f"[DB] cargar error: {e}"); return None

def registrar_log(usuario: str, accion: str) -> None:
    try:
        conn, engine = get_connection()
        cur = conn.cursor()
        p = _p(engine)
        cur.execute(f"INSERT INTO sync_log (usuario,accion) VALUES ({p},{p})", (usuario, accion))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[DB] log error: {e}")

def ultimo_log(limite: int = 10) -> list:
    try:
        conn, engine = get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT usuario,accion,creado_en FROM sync_log ORDER BY creado_en DESC LIMIT {_p(engine)}", (limite,))
        rows = cur.fetchall(); conn.close()
        return [{"usuario": r[0], "accion": r[1], "creado_en": str(r[2])} for r in rows]
    except: return []
