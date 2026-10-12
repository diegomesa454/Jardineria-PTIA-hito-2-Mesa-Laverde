from simulator.simulador import generar_dataset


def test_dataset_estructura_y_reproducibilidad():
    a = generar_dataset(plantas_por_especie=10, dias=15, semilla=1)
    b = generar_dataset(plantas_por_especie=10, dias=15, semilla=1)
    assert a.equals(b)
    assert len(a) == 3 * 10 * 15
    assert set(a["estado"]) <= {"Saludable", "Atención", "Crítico"}
    assert set(a["tendencia"].dropna()) <= {"Mejora", "Estable", "Empeora"}


def test_particion_por_planta_sin_fuga():
    df = generar_dataset(plantas_por_especie=20, dias=10, semilla=3)
    por_planta = df.groupby("planta_id")["particion"].nunique()
    assert (por_planta == 1).all()  # ninguna planta aparece en dos particiones


def test_ultimos_dias_sin_tendencia():
    df = generar_dataset(plantas_por_especie=5, dias=10, semilla=2)
    assert df[df["dia"] >= 7]["tendencia"].isna().all()
