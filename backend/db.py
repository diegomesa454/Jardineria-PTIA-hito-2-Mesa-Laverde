"""Almacenamiento en SQLite (plantas y reportes diarios)."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

RUTA_DB = Path(os.environ.get("JARDINERIA_DB", Path(__file__).resolve().parent / "jardineria.sqlite"))

ESQUEMA = """
CREATE TABLE IF NOT EXISTS plantas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  especie TEXT NOT NULL,
  fecha_siembra TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reportes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  planta_id INTEGER NOT NULL REFERENCES plantas(id) ON DELETE CASCADE,
  fecha TEXT NOT NULL,
  humedad TEXT, color_hojas TEXT, turgencia TEXT, riego_hoy TEXT,
  horas_sol REAL, temperatura_c REAL, plagas TEXT,
  diagnostico TEXT,
  UNIQUE (planta_id, fecha)
);
"""


@contextmanager
def conexion():
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def iniciar():
    with conexion() as con:
        con.executescript(ESQUEMA)


def a_json(d):
    return json.dumps(d, ensure_ascii=False)
