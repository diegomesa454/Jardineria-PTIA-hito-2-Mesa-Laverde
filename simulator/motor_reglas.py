"""Motor de reglas de JardinerIA (componente 2 de la arquitectura, sección 6.4).

Lee la base de conocimiento (carpeta knowledge/) y, dado un reporte diario:
  - calcula el índice de estrés,
  - lo convierte en estado (Saludable / Atención / Crítico),
  - devuelve las reglas activas (causa probable, acciones y explicación).

Un reporte es un diccionario con las claves: humedad, color_hojas, turgencia,
riego_hoy, horas_sol, temperatura_c, plagas.
"""
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
RUTA_KB = RAIZ / "knowledge"
ESPECIES = ("albahaca", "lechuga", "tomate_cherry")


def _leer(nombre):
    with open(RUTA_KB / f"{nombre}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_kb():
    """Devuelve {'comunes': {...}, 'albahaca': {...}, 'lechuga': {...}, 'tomate_cherry': {...}}."""
    kb = {"comunes": _leer("comunes")}
    for esp in ESPECIES:
        kb[esp] = _leer(esp)
    return kb


def calcular_indice(reporte, especie, kb):
    """Suma los puntos de estrés de cada condición presente (ver comunes.yaml)."""
    p = kb["comunes"]["indice_estres"]["puntos"]
    r = kb[especie]["rangos"]
    total = 0

    if reporte["humedad"] == "Seco":
        total += p["humedad_seco"]
    elif reporte["humedad"] == "Encharcado":
        total += p["humedad_encharcado"]

    if reporte["turgencia"] == "Caída leve":
        total += p["turgencia_caida_leve"]
    elif reporte["turgencia"] == "Marchita":
        total += p["turgencia_marchita"]

    if reporte["color_hojas"] == "Amarillas":
        total += p["hojas_amarillas"]
    elif reporte["color_hojas"] == "Puntas marrones":
        total += p["hojas_puntas_marrones"]
    elif reporte["color_hojas"] == "Manchas":
        total += p["hojas_manchas"]

    if reporte["plagas"] == "Sí":
        total += p["plagas_si"]

    t = reporte["temperatura_c"]
    t_opt, t_tol = r["temperatura_c"]["optima"], r["temperatura_c"]["tolerable"]
    if t < t_tol[0] or t > t_tol[1]:
        total += p["temperatura_fuera_de_tolerable"]
    elif t < t_opt[0] or t > t_opt[1]:
        total += p["temperatura_fuera_de_optima_pero_tolerable"]

    if reporte["horas_sol"] < r["horas_sol"]["minimo"]:
        total += p["sol_bajo_el_minimo"]

    return total


def estado_desde_indice(indice, kb):
    """Convierte el índice en Saludable / Atención / Crítico según los umbrales."""
    for nombre, (lo, hi) in kb["comunes"]["indice_estres"]["estado"].items():
        if lo <= indice <= hi:
            return nombre
    raise ValueError(f"Índice fuera de rango: {indice}")


def _cumple(condicion, valor):
    """Una condición es una lista de valores aceptados o un dict con '<' / '>'."""
    if isinstance(condicion, list):
        return valor in condicion
    if isinstance(condicion, dict):
        for op, umbral in condicion.items():
            if op == "<" and not valor < umbral:
                return False
            if op == ">" and not valor > umbral:
                return False
        return True
    return False


def reglas_activas(reporte, especie, kb):
    """Reglas (comunes + de la especie) cuyas condiciones se cumplen en el reporte."""
    reglas = kb["comunes"]["reglas_comunes"] + kb[especie]["reglas_especificas"]
    activas = []
    for regla in reglas:
        if all(_cumple(cond, reporte[campo]) for campo, cond in regla["si"].items()):
            activas.append(regla)
    return activas
