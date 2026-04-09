# 🏭 Sistema de Turnos — Streamlit + SQLite

Migración completa de la aplicación HTML/JS a Python/Streamlit con persistencia en SQLite.

## 📁 Estructura

```
sistema-turnos/
├── app.py                  # Punto de entrada Streamlit
├── requirements.txt
├── .gitignore
├── database/
│   ├── __init__.py
│   └── db.py               # CRUD + inicialización SQLite
├── modules/
│   ├── __init__.py
│   ├── logic.py            # Lógica de negocio (rotación, HE, ausencias…)
│   └── ui_helpers.py       # Componentes UI reutilizables
└── .streamlit/
    └── config.toml         # Tema y configuración del servidor
```

## 🚀 Instalación y ejecución

```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar
streamlit run app.py
```

La base de datos `db.sqlite3` se crea automáticamente al primer arranque.

## 🔐 Credenciales por defecto

| Usuario | Contraseña |
|---------|------------|
| admin   | admin123   |
| super   | super123   |

Cámbialas directamente en la tabla `usuarios` de SQLite.

## 🔌 Migrar a PostgreSQL

En `database/db.py`, reemplaza `get_connection()`:

```python
import psycopg2, os

@contextmanager
def get_connection():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.row_factory = ...  # adaptar según psycopg2
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()
```

Y ajusta las sentencias SQL (`?` → `%s`, `ON CONFLICT` → sintaxis PostgreSQL).

## ☁️ Despliegue en Streamlit Cloud

1. Sube el proyecto a GitHub (sin el `.sqlite3`).
2. Conecta el repo en [share.streamlit.io](https://share.streamlit.io).
3. Configura `DB_PATH` como variable de entorno si usas un volumen persistente,  
   o usa PostgreSQL con `DATABASE_URL`.

## 📦 Módulos

| Módulo | Funcionalidad |
|--------|---------------|
| Turnos | Tabla semanal, rotación A/B/C, horas extras (7 tipos CST), ausencias CRUD |
| Compensatorios | Saldo CHE ganado vs. usado, importación Excel |
| Vacaciones | Períodos, días acumulados, alertas ≥15 días, importación Excel |
| Cumpleaños | Lista, disponibles hoy, próximos 30 días, importación Excel |
| Centro de Costos | CC Inscrito vs. Actual por operario, importación Excel |
