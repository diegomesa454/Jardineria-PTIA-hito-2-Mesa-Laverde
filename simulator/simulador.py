"""Simulador de plantas virtuales de JardinerIA (sección 6.5, "Datos de entrenamiento").

Genera trayectorias diarias de plantas virtuales de las tres especies a partir de un
modelo sencillo de balance hídrico y estrés, con variables latentes:
  - m: humedad del sustrato (0 = seco, 1 = saturado)
  - h: salud de la planta (0 = muy mala, 1 = excelente), con inercia
y perfiles de jardinero (cuidadoso, sobrerregador, olvidadizo, irregular).

Cada día se produce:
  - un reporte "verdadero" (sin ruido), con el que se calcula el índice de estrés y se
    etiqueta el estado (así las etiquetas dependen solo de la base de conocimiento), y
  - un reporte "observado" con ruido de percepción (lo que el usuario diría), que es
    la entrada que verá el modelo.
La tendencia compara el índice del día con el de 3 días después.

Uso:
    python -m simulator.simulador --plantas 200 --dias 30 --semilla 42 \
        --salida data/dataset_simulado.csv

LIMITACIÓN: los datos son simulados. Las métricas obtenidas con ellos miden la
coherencia con la base de conocimiento, no el desempeño con plantas reales.
"""
import argparse

import numpy as np
import pandas as pd

from simulator.motor_reglas import ESPECIES, cargar_kb, calcular_indice, estado_desde_indice

HUMEDAD = ["Seco", "Húmedo", "Encharcado"]
TURGENCIA = ["Firme", "Caída leve", "Marchita"]
COLORES = ["Verde normal", "Amarillas", "Puntas marrones", "Manchas"]

# Perfiles de jardinero: (probabilidad de regar, regla de decisión, cantidad)
PERFILES = {
    "cuidadoso":     {"peso": 0.35},
    "sobrerregador": {"peso": 0.20},
    "olvidadizo":    {"peso": 0.25},
    "irregular":     {"peso": 0.20},
}

# Ruido de percepción del usuario (probabilidad de reportar una categoría vecina)
RUIDO = {"humedad": 0.12, "turgencia": 0.15, "color_hojas": 0.12, "plagas": 0.05}
SIGMA_TEMP = 1.5   # °C, error de estimación de la temperatura
SIGMA_SOL = 1.0    # horas, error de estimación de las horas de sol

TENDENCIA_VENTANA = 3  # días hacia adelante


def _riego(perfil, m, rng):
    """Devuelve (etiqueta de riego, aporte de humedad) según el perfil del jardinero."""
    if perfil == "cuidadoso":
        if m < 0.40 and rng.random() < 0.85:
            return "Suficiente", 0.50
    elif perfil == "sobrerregador":
        if rng.random() < 0.60:
            return ("Exceso", 0.70) if rng.random() < 0.6 else ("Suficiente", 0.50)
    elif perfil == "olvidadizo":
        if m < 0.50 and rng.random() < 0.20:
            return ("Poco", 0.25) if rng.random() < 0.6 else ("Suficiente", 0.50)
    else:  # irregular
        if rng.random() < 0.40:
            etiqueta = rng.choice(["Poco", "Suficiente", "Exceso"])
            return etiqueta, {"Poco": 0.25, "Suficiente": 0.50, "Exceso": 0.70}[etiqueta]
    return "No", 0.0


def _categoria_vecina(valor, lista, rng, p):
    """Con probabilidad p devuelve una categoría vecina en la escala ordinal."""
    if rng.random() >= p:
        return valor
    i = lista.index(valor)
    vecinos = [j for j in (i - 1, i + 1) if 0 <= j < len(lista)]
    return lista[int(rng.choice(vecinos))]


def simular_planta(planta_id, especie, dias, kb, rng):
    """Simula una planta y devuelve una lista de filas (una por día)."""
    r = kb[especie]["rangos"]
    t_opt_max = r["temperatura_c"]["optima"][1]

    perfil = rng.choice(list(PERFILES), p=[v["peso"] for v in PERFILES.values()])
    base_temp = rng.uniform(13, 30)
    base_sol = rng.uniform(4, 10)

    m = rng.uniform(0.40, 0.70)
    h = 0.90
    plagas = False
    racha_hum, racha_seco, ola_calor = 0, 0, 0
    filas = []

    for dia in range(dias):
        # --- clima del día ---
        if ola_calor > 0:
            ola_calor -= 1
        elif rng.random() < 0.03:
            ola_calor = 3
        temp = base_temp + rng.normal(0, 2.5) + (5 if ola_calor > 0 else 0)
        sol = float(np.clip(base_sol + rng.normal(0, 1.5), 0, 12))

        # --- el jardinero corrige su cuidado si la planta se ve mal ---
        if h < 0.55 and perfil != "cuidadoso" and rng.random() < 0.25:
            perfil = "cuidadoso"

        # --- riego y balance hídrico ---
        etiqueta_riego, aporte = _riego(perfil, m, rng)
        evap = 0.05 + 0.006 * max(0.0, temp - 15) + 0.006 * sol
        m = m - evap + aporte
        if m > 0.80:
            m -= 0.08  # drenaje lento
        m = float(np.clip(m, 0.0, 1.0))

        racha_hum = racha_hum + 1 if m > 0.75 else 0
        racha_seco = racha_seco + 1 if m < 0.20 else 0

        # --- plagas (proceso de Markov) ---
        if plagas:
            plagas = rng.random() > 0.20
        else:
            plagas = rng.random() < (0.04 if h < 0.5 else 0.02)

        # --- estrés y salud (con inercia) ---
        s = 0.0
        if m < 0.20:
            s += 0.15
        if m < 0.10:
            s += 0.15
        if m > 0.85:
            s += 0.12
        t_opt, t_tol = r["temperatura_c"]["optima"], r["temperatura_c"]["tolerable"]
        if temp < t_tol[0] or temp > t_tol[1]:
            s += 0.12
        elif temp < t_opt[0] or temp > t_opt[1]:
            s += 0.04
        if sol < r["horas_sol"]["minimo"]:
            s += 0.05
        if plagas:
            s += 0.08
        h = float(np.clip(h - 0.5 * s + (0.06 if s < 0.05 else 0.0), 0.0, 1.0))

        # --- reporte verdadero (sin ruido) ---
        humedad = "Seco" if m < 0.25 else "Encharcado" if m > 0.80 else "Húmedo"
        if h < 0.35 or m < 0.08:
            turgencia = "Marchita"
        elif h < 0.65 or m < 0.18:
            turgencia = "Caída leve"
        else:
            turgencia = "Firme"

        if racha_hum >= 3 and rng.random() < 0.5:
            color = "Manchas"
        elif (h < 0.60 and m > 0.70) or h < 0.45:
            color = "Amarillas"
        elif (m < 0.20 and temp > t_opt_max) or (racha_seco >= 3 and rng.random() < 0.5):
            color = "Puntas marrones"
        else:
            color = "Verde normal"

        verdadero = {
            "humedad": humedad,
            "color_hojas": color,
            "turgencia": turgencia,
            "riego_hoy": etiqueta_riego,
            "horas_sol": sol,
            "temperatura_c": temp,
            "plagas": "Sí" if plagas else "No",
        }
        indice = calcular_indice(verdadero, especie, kb)

        # --- reporte observado (con ruido de percepción) ---
        obs_color = color
        if rng.random() < RUIDO["color_hojas"]:
            obs_color = str(rng.choice([c for c in COLORES if c != color]))
        observado = {
            "humedad": _categoria_vecina(humedad, HUMEDAD, rng, RUIDO["humedad"]),
            "color_hojas": obs_color,
            "turgencia": _categoria_vecina(turgencia, TURGENCIA, rng, RUIDO["turgencia"]),
            "riego_hoy": etiqueta_riego,
            "horas_sol": round(float(np.clip(sol + rng.normal(0, SIGMA_SOL), 0, 12)), 1),
            "temperatura_c": round(temp + rng.normal(0, SIGMA_TEMP), 1),
            "plagas": ("Sí" if plagas else "No") if rng.random() >= RUIDO["plagas"]
                      else ("No" if plagas else "Sí"),
        }

        filas.append({
            "planta_id": planta_id,
            "especie": especie,
            "dia": dia,
            "dias_desde_siembra": None,  # se completa al final de la simulación
            **observado,
            "indice_estres": indice,
        })

    # días desde la siembra: arranque aleatorio + día
    arranque = int(rng.integers(10, 40))
    for f in filas:
        f["dias_desde_siembra"] = arranque + f["dia"]
    return filas


def generar_dataset(plantas_por_especie=200, dias=30, semilla=42):
    """Genera el dataset completo, con estado, tendencia y partición por planta."""
    rng = np.random.default_rng(semilla)
    kb = cargar_kb()

    filas = []
    pid = 0
    for esp in ESPECIES:
        for _ in range(plantas_por_especie):
            filas.extend(simular_planta(pid, esp, dias, kb, rng))
            pid += 1
    df = pd.DataFrame(filas)

    # Estado (a partir del índice verdadero)
    df["estado"] = [estado_desde_indice(i, kb) for i in df["indice_estres"]]

    # Tendencia: índice del día vs índice 3 días después (misma planta)
    df["indice_estres_t3"] = df.groupby("planta_id")["indice_estres"].shift(-TENDENCIA_VENTANA)
    delta = df["indice_estres_t3"] - df["indice_estres"]
    df["tendencia"] = np.select([delta <= -1, delta >= 1], ["Mejora", "Empeora"], default="Estable")
    df.loc[df["indice_estres_t3"].isna(), "tendencia"] = np.nan

    # Partición por planta (no por día): 70 % / 15 % / 15 %
    plantas = df["planta_id"].unique()
    rng.shuffle(plantas)
    n = len(plantas)
    corte1, corte2 = int(0.70 * n), int(0.85 * n)
    particion = {p: "entrenamiento" for p in plantas[:corte1]}
    particion.update({p: "validacion" for p in plantas[corte1:corte2]})
    particion.update({p: "prueba" for p in plantas[corte2:]})
    df["particion"] = df["planta_id"].map(particion)
    return df


def main():
    ap = argparse.ArgumentParser(description="Genera el dataset simulado de JardinerIA")
    ap.add_argument("--plantas", type=int, default=200, help="plantas por especie")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--salida", default="data/dataset_simulado.csv")
    a = ap.parse_args()

    df = generar_dataset(a.plantas, a.dias, a.semilla)
    df.to_csv(a.salida, index=False, encoding="utf-8")
    print(f"Dataset guardado en {a.salida}: {len(df)} filas, {df['planta_id'].nunique()} plantas")
    print("\nEstado:\n", df["estado"].value_counts(normalize=True).round(3).to_string())
    print("\nTendencia:\n", df["tendencia"].value_counts(normalize=True).round(3).to_string())


if __name__ == "__main__":
    main()
