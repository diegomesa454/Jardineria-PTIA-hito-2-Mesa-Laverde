from simulator.motor_reglas import (ESPECIES, cargar_kb, calcular_indice,
                                     estado_desde_indice, reglas_activas)

KB = cargar_kb()

SANA = {"humedad": "Húmedo", "color_hojas": "Verde normal", "turgencia": "Firme",
        "riego_hoy": "Suficiente", "horas_sol": 8, "temperatura_c": 22, "plagas": "No"}


def test_kb_sin_booleanos_en_riego():
    # "No" sin comillas en YAML se lee como False; debe leerse como texto
    assert KB["comunes"]["campos_reporte"]["riego_hoy"]["valores"][0] == "No"


def test_planta_sana_es_saludable():
    for esp in ESPECIES:
        r = dict(SANA, temperatura_c=20)
        assert calcular_indice(r, esp, KB) == 0
        assert estado_desde_indice(0, KB) == "Saludable"


def test_planta_marchita_y_seca_es_critica():
    r = dict(SANA, humedad="Seco", turgencia="Marchita", color_hojas="Puntas marrones")
    idx = calcular_indice(r, "albahaca", KB)
    assert idx >= 4
    assert estado_desde_indice(idx, KB) == "Crítico"


def test_regla_exceso_de_riego_se_activa():
    r = dict(SANA, humedad="Encharcado", color_hojas="Amarillas")
    ids = [x["id"] for x in reglas_activas(r, "lechuga", KB)]
    assert "C1" in ids


def test_regla_riego_irregular_tomate_usa_texto_no():
    r = dict(SANA, humedad="Seco", riego_hoy="No")
    ids = [x["id"] for x in reglas_activas(r, "tomate_cherry", KB)]
    assert "T2" in ids
