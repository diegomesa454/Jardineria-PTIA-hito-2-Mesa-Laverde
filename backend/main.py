"""API de JardinerIA.  Ejecutar desde la raíz del repo:  uvicorn backend.main:app --reload"""
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend import db
from backend.servicio import CAMPOS, Diagnosticador
from simulator.motor_reglas import ESPECIES

import json

FRONT = Path(__file__).resolve().parent.parent / "frontend"
Especie = Literal["albahaca", "lechuga", "tomate_cherry"]


class Reporte(BaseModel):
    humedad: Literal["Seco", "Húmedo", "Encharcado"]
    color_hojas: Literal["Verde normal", "Amarillas", "Puntas marrones", "Manchas"]
    turgencia: Literal["Firme", "Caída leve", "Marchita"]
    riego_hoy: Literal["No", "Poco", "Suficiente", "Exceso"]
    horas_sol: float = Field(ge=0, le=12)
    temperatura_c: float = Field(ge=-10, le=50)
    plagas: Literal["No", "Sí"]
    fecha: Optional[date] = None


class PlantaNueva(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    especie: Especie
    dias_desde_siembra: int = Field(default=0, ge=0, le=400)


class ReporteDia(BaseModel):
    """Un día del historial para el diagnóstico sin base de datos."""
    dias_desde_siembra: int = Field(ge=0)
    humedad: Literal["Seco", "Húmedo", "Encharcado"]
    color_hojas: Literal["Verde normal", "Amarillas", "Puntas marrones", "Manchas"]
    turgencia: Literal["Firme", "Caída leve", "Marchita"]
    riego_hoy: Literal["No", "Poco", "Suficiente", "Exceso"]
    horas_sol: float = Field(ge=0, le=12)
    temperatura_c: float = Field(ge=-10, le=50)
    plagas: Literal["No", "Sí"]


class DiagnosticoSuelto(BaseModel):
    """Diagnóstico sin guardar nada: `historial` va de más antiguo a más reciente y `reporte` es el de hoy."""
    especie: Especie
    reporte: ReporteDia
    historial: list[ReporteDia] = []


@asynccontextmanager
async def ciclo_vida(app):
    db.iniciar()
    app.state.diag = Diagnosticador()
    yield


app = FastAPI(title="JardinerIA", version="1.0", lifespan=ciclo_vida)


def _planta(con, pid):
    p = con.execute("SELECT * FROM plantas WHERE id = ?", (pid,)).fetchone()
    if not p:
        raise HTTPException(404, "Planta no encontrada")
    return p


def _historial(con, planta, hasta):
    """Reportes de la planta hasta `hasta` (inclusive), en formato del servicio."""
    filas = con.execute(
        "SELECT * FROM reportes WHERE planta_id = ? AND fecha <= ? ORDER BY fecha DESC LIMIT 14",
        (planta["id"], hasta.isoformat())).fetchall()
    siembra = date.fromisoformat(planta["fecha_siembra"])
    out = []
    for f in reversed(filas):
        fecha = date.fromisoformat(f["fecha"])
        out.append({"fecha": fecha, "dias_desde_siembra": max((fecha - siembra).days, 0),
                    **{c: f[c] for c in CAMPOS}})
    return out


# ------------------------------------------------------------------ sistema
@app.get("/api/salud")
def salud():
    d = app.state.diag
    return {"estado": "ok", "modo": d.modo, "error_modelos": d.error_modelos}


@app.get("/api/especies")
def especies():
    return list(ESPECIES)


# ------------------------------------------------------------------ plantas
@app.post("/api/plantas", status_code=201)
def crear_planta(p: PlantaNueva):
    siembra = date.today() - timedelta(days=p.dias_desde_siembra)
    with db.conexion() as con:
        cur = con.execute("INSERT INTO plantas (nombre, especie, fecha_siembra) VALUES (?, ?, ?)",
                          (p.nombre.strip(), p.especie, siembra.isoformat()))
        return {"id": cur.lastrowid, "nombre": p.nombre.strip(), "especie": p.especie,
                "fecha_siembra": siembra.isoformat()}


@app.get("/api/plantas")
def listar_plantas():
    with db.conexion() as con:
        out = []
        for p in con.execute("SELECT * FROM plantas ORDER BY id").fetchall():
            u = con.execute("SELECT fecha, diagnostico FROM reportes WHERE planta_id = ? "
                            "ORDER BY fecha DESC LIMIT 1", (p["id"],)).fetchone()
            diag = json.loads(u["diagnostico"]) if u else None
            out.append({**dict(p),
                        "ultimo_reporte": u["fecha"] if u else None,
                        "ultimo_estado": diag["estado"] if diag else None,
                        "ultima_tendencia": diag["tendencia_3_dias"] if diag else None})
        return out


@app.delete("/api/plantas/{pid}", status_code=204)
def borrar_planta(pid: int):
    with db.conexion() as con:
        _planta(con, pid)
        con.execute("DELETE FROM plantas WHERE id = ?", (pid,))


# ------------------------------------------------------------------ reportes
@app.post("/api/plantas/{pid}/reportes")
def enviar_reporte(pid: int, r: Reporte):
    fecha = r.fecha or date.today()
    with db.conexion() as con:
        planta = _planta(con, pid)
        if fecha < date.fromisoformat(planta["fecha_siembra"]):
            raise HTTPException(422, "La fecha es anterior a la siembra")
        # Guarda primero el reporte (si ya había uno ese día, lo reemplaza) para que entre al historial
        con.execute(
            "INSERT INTO reportes (planta_id, fecha, humedad, color_hojas, turgencia, riego_hoy, horas_sol, "
            "temperatura_c, plagas) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(planta_id, fecha) DO UPDATE SET humedad=excluded.humedad, "
            "color_hojas=excluded.color_hojas, turgencia=excluded.turgencia, riego_hoy=excluded.riego_hoy, "
            "horas_sol=excluded.horas_sol, temperatura_c=excluded.temperatura_c, plagas=excluded.plagas",
            (pid, fecha.isoformat(), *[getattr(r, c) for c in CAMPOS]))
        resultado = app.state.diag.diagnosticar(planta["especie"], _historial(con, planta, fecha))
        con.execute("UPDATE reportes SET diagnostico = ? WHERE planta_id = ? AND fecha = ?",
                    (db.a_json(resultado), pid, fecha.isoformat()))
    return {"planta_id": pid, "fecha": fecha.isoformat(), **resultado}


@app.get("/api/plantas/{pid}/reportes")
def historial(pid: int):
    with db.conexion() as con:
        _planta(con, pid)
        filas = con.execute("SELECT * FROM reportes WHERE planta_id = ? ORDER BY fecha DESC", (pid,)).fetchall()
        return [{**{k: f[k] for k in ["fecha", *CAMPOS]},
                 "diagnostico": json.loads(f["diagnostico"]) if f["diagnostico"] else None} for f in filas]


# ------------------------------------------------------------------ diagnóstico sin guardar
@app.post("/api/diagnostico")
def diagnostico_suelto(d: DiagnosticoSuelto):
    """Útil para probar escenarios sin tocar la base de datos."""
    dias = d.historial + [d.reporte]
    hoy = date.today()
    hist = [{"fecha": hoy - timedelta(days=len(dias) - 1 - i), **x.model_dump()} for i, x in enumerate(dias)]
    return app.state.diag.diagnosticar(d.especie, hist)


# ------------------------------------------------------------------ interfaz
@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(FRONT / "app.html")


@app.get("/prototipo", include_in_schema=False)
def prototipo():
    return FileResponse(FRONT / "prototipo_interfaz.html")
