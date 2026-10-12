"""Construcción de características para el modelo de estado y tendencia (sección 6.5).

Entradas del modelo (por planta y día):
  - los 7 campos del reporte observado (categorías ordinales como enteros),
  - la especie (variables indicadoras) y los días desde la siembra,
  - variables derivadas sobre la ventana de los últimos días: cambio de humedad entre
    días, días desde el último riego, promedio de horas de sol, desviación de la
    temperatura respecto al rango óptimo de la especie y el índice de estrés
    calculado por las reglas sobre el reporte observado (y su evolución).
"""
import numpy as np
import pandas as pd

from simulator.motor_reglas import ESPECIES, cargar_kb, calcular_indice, estado_desde_indice

ORD = {
    "humedad": {"Seco": 0, "Húmedo": 1, "Encharcado": 2},
    "turgencia": {"Firme": 0, "Caída leve": 1, "Marchita": 2},
    "riego_hoy": {"No": 0, "Poco": 1, "Suficiente": 2, "Exceso": 3},
    "plagas": {"No": 0, "Sí": 1},
}
COLORES = ["Verde normal", "Amarillas", "Puntas marrones", "Manchas"]
VENTANA = 3  # días previos usados como historial


def _desviacion_temperatura(temp, esp, kb):
    lo, hi = kb[esp]["rangos"]["temperatura_c"]["optima"]
    return np.where(temp < lo, lo - temp, np.where(temp > hi, temp - hi, 0.0))


def indice_observado(df, kb):
    """Índice de estrés de las reglas aplicado al reporte OBSERVADO (línea base)."""
    return np.array([
        calcular_indice(fila, fila["especie"], kb)
        for fila in df[["especie", "humedad", "color_hojas", "turgencia", "riego_hoy",
                        "horas_sol", "temperatura_c", "plagas"]].to_dict("records")
    ])


def construir_caracteristicas(df, kb=None):
    """Devuelve (X, df_ordenado). X es un DataFrame numérico alineado con df_ordenado."""
    kb = kb or cargar_kb()
    df = df.sort_values(["planta_id", "dia"]).reset_index(drop=True).copy()

    # Codificación del reporte del día
    for campo, mapa in ORD.items():
        df[campo + "_n"] = df[campo].map(mapa)
    for c in COLORES:
        df["color_" + c.replace(" ", "_").lower()] = (df["color_hojas"] == c).astype(int)

    df["idx_obs"] = indice_observado(df, kb)
    df["desv_temp"] = [
        float(_desviacion_temperatura(np.array([t]), e, kb)[0])
        for t, e in zip(df["temperatura_c"], df["especie"])
    ]

    g = df.groupby("planta_id")
    base = ["humedad_n", "turgencia_n", "riego_hoy_n", "plagas_n", "horas_sol",
            "temperatura_c", "idx_obs", "desv_temp"]

    # Valores de los días previos (si no hay historial, se repite el valor del día)
    for k in range(1, VENTANA + 1):
        for c in base:
            df[f"{c}_lag{k}"] = g[c].shift(k)
            df[f"{c}_lag{k}"] = df[f"{c}_lag{k}"].fillna(df[c])

    # Variables derivadas sobre la ventana
    df["cambio_humedad"] = df["humedad_n"] - df["humedad_n_lag1"]
    df["cambio_idx_obs"] = df["idx_obs"] - df["idx_obs_lag3"]
    df["prom_idx_obs"] = df[["idx_obs"] + [f"idx_obs_lag{k}" for k in range(1, VENTANA + 1)]].mean(axis=1)
    df["prom_horas_sol"] = df[["horas_sol"] + [f"horas_sol_lag{k}" for k in range(1, VENTANA + 1)]].mean(axis=1)
    df["prom_temp"] = df[["temperatura_c"] + [f"temperatura_c_lag{k}" for k in range(1, VENTANA + 1)]].mean(axis=1)

    # Días desde el último riego (cualquier riego distinto de "No")
    dias = []
    for _, grupo in df.groupby("planta_id", sort=False):
        contador, salida = 10, []
        for r in grupo["riego_hoy_n"]:
            contador = 0 if r > 0 else min(contador + 1, 10)
            salida.append(contador)
        dias.extend(salida)
    df["dias_desde_riego"] = dias

    for esp in ESPECIES:
        df["esp_" + esp] = (df["especie"] == esp).astype(int)

    cols = (["dias_desde_siembra", "humedad_n", "turgencia_n", "riego_hoy_n", "plagas_n",
             "horas_sol", "temperatura_c"]
            + [c for c in df.columns if c.startswith("color_") and c != "color_hojas"]
            + ["idx_obs", "desv_temp", "cambio_humedad", "cambio_idx_obs", "prom_idx_obs",
               "prom_horas_sol", "prom_temp", "dias_desde_riego"]
            + [f"{c}_lag{k}" for k in range(1, VENTANA + 1) for c in base]
            + ["esp_" + e for e in ESPECIES])
    return df[cols].astype(float), df


def estado_reglas(df, kb=None):
    """Línea base de estado: solo reglas sobre el reporte observado."""
    kb = kb or cargar_kb()
    return np.array([estado_desde_indice(i, kb) for i in df["idx_obs"]])


def tendencia_reglas(df):
    """Línea base de tendencia: extrapola el cambio reciente del índice observado."""
    delta = df["idx_obs"] - df["idx_obs_lag3"]
    return np.select([delta >= 1, delta <= -1], ["Empeora", "Mejora"], default="Estable")
