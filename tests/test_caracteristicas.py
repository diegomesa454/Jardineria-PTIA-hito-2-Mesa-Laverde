from simulator.caracteristicas import construir_caracteristicas
from simulator.simulador import generar_dataset


def test_caracteristicas_sin_nulos_y_alineadas():
    df = generar_dataset(plantas_por_especie=5, dias=12, semilla=7)
    X, d = construir_caracteristicas(df)
    assert len(X) == len(d) == len(df)
    assert X.isna().sum().sum() == 0


def test_historial_no_usa_el_futuro():
    df = generar_dataset(plantas_por_especie=3, dias=10, semilla=9)
    X, d = construir_caracteristicas(df)
    # el valor "lag1" de un día debe ser el valor del día anterior de la misma planta
    p = d[d["planta_id"] == d["planta_id"].iloc[0]].index
    assert X.loc[p[5], "humedad_n_lag1"] == X.loc[p[4], "humedad_n"]
