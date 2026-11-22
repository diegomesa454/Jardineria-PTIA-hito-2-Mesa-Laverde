"""Pruebas del backend. Si los modelos no están en models/, las pruebas corren en modo reglas."""
import os
import tempfile
from datetime import date, timedelta

import pytest

os.environ["JARDINERIA_DB"] = os.path.join(tempfile.mkdtemp(), "prueba.sqlite")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

BUENO = {"humedad": "Húmedo", "color_hojas": "Verde normal", "turgencia": "Firme", "riego_hoy": "Suficiente",
         "horas_sol": 8, "temperatura_c": 24, "plagas": "No"}
MALO = {"humedad": "Encharcado", "color_hojas": "Amarillas", "turgencia": "Marchita", "riego_hoy": "Exceso",
        "horas_sol": 3, "temperatura_c": 24, "plagas": "Sí"}


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def test_salud(cliente):
    r = cliente.get("/api/salud").json()
    assert r["estado"] == "ok" and r["modo"] in ("modelo", "reglas")


def test_planta_sana_y_critica(cliente):
    sana = cliente.post("/api/plantas", json={"nombre": "A", "especie": "albahaca", "dias_desde_siembra": 30}).json()
    r = cliente.post(f"/api/plantas/{sana['id']}/reportes", json=BUENO).json()
    assert r["estado"] == "Saludable" and r["indice_estres"] <= 1

    mala = cliente.post("/api/plantas", json={"nombre": "B", "especie": "albahaca", "dias_desde_siembra": 30}).json()
    r = cliente.post(f"/api/plantas/{mala['id']}/reportes", json=MALO).json()
    assert r["estado"] == "Crítico"
    assert r["acciones"] and any(c["id"] == "C3" for c in r["causas_probables"])


def test_historial_y_reemplazo_del_mismo_dia(cliente):
    p = cliente.post("/api/plantas", json={"nombre": "C", "especie": "lechuga", "dias_desde_siembra": 20}).json()
    for i in (2, 1, 0):
        cliente.post(f"/api/plantas/{p['id']}/reportes", json={**BUENO, "fecha": str(date.today() - timedelta(days=i))})
    cliente.post(f"/api/plantas/{p['id']}/reportes", json=MALO)  # reemplaza el de hoy
    h = cliente.get(f"/api/plantas/{p['id']}/reportes").json()
    assert len(h) == 3 and h[0]["humedad"] == "Encharcado"
    assert h[0]["diagnostico"]["dias_de_historial"] == 3


def test_validaciones(cliente):
    p = cliente.post("/api/plantas", json={"nombre": "D", "especie": "tomate_cherry"}).json()
    assert cliente.post(f"/api/plantas/{p['id']}/reportes", json={**BUENO, "humedad": "Mojado"}).status_code == 422
    assert cliente.post(f"/api/plantas/{p['id']}/reportes", json={**BUENO, "horas_sol": 30}).status_code == 422
    assert cliente.post("/api/plantas/9999/reportes", json=BUENO).status_code == 404
    assert cliente.post("/api/plantas", json={"nombre": "X", "especie": "rosa"}).status_code == 422


def test_diagnostico_suelto_y_borrado(cliente):
    r = cliente.post("/api/diagnostico", json={"especie": "tomate_cherry", "reporte": {**BUENO, "dias_desde_siembra": 40}})
    assert r.status_code == 200 and r.json()["aviso_historial"]
    p = cliente.post("/api/plantas", json={"nombre": "E", "especie": "albahaca"}).json()
    assert cliente.delete(f"/api/plantas/{p['id']}").status_code == 204
    assert all(x["id"] != p["id"] for x in cliente.get("/api/plantas").json())


def test_interfaz(cliente):
    assert "JardinerIA" in cliente.get("/").text
