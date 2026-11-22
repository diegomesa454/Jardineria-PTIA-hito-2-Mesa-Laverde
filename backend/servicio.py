"""Servicio de diagnóstico de JardinerIA.

Flujo (arquitectura 6.4): reporte -> características (ventana de 3 días) -> modelo de estado y
de tendencia (Random Forest) -> motor de reglas (causa probable, acciones, explicación).

Si los modelos no están en models/, el servicio sigue funcionando en "modo reglas"
(solo base de conocimiento), para que la demo no se caiga.
"""
import sys
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from simulator.caracteristicas import construir_caracteristicas, tendencia_reglas
from simulator.motor_reglas import cargar_kb, estado_desde_indice, reglas_activas

RAIZ = Path(__file__).resolve().parent.parent
RUTA_MODELOS = RAIZ / "models"
CAMPOS = ["humedad", "color_hojas", "turgencia", "riego_hoy", "horas_sol", "temperatura_c", "plagas"]
MAX_HISTORIAL = 14  # días previos usados (el modelo mira 3; el resto cubre "días desde el último riego")


class EnvolturaSklearn:
    """Réplica de la clase del script hito3_comparacion_modelos.py.

    Los .joblib se guardaron desde ese script, así que joblib busca la clase en __main__.
    Registrarla aquí permite cargarlos sin volver a entrenar.
    """

    def __init__(self, modelo=None):
        self.modelo = modelo


def _cargar(ruta):
    import __main__
    __main__.EnvolturaSklearn = EnvolturaSklearn
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        obj = joblib.load(ruta)
    modelo = getattr(obj, "modelo", obj)
    if hasattr(modelo, "n_jobs"):
        modelo.n_jobs = 1  # una sola muestra: paralelizar solo añade latencia
    return modelo


class Diagnosticador:
    def __init__(self, ruta_modelos=RUTA_MODELOS):
        self.kb = cargar_kb()
        self.modo = "reglas"
        self.modelo_estado = self.modelo_tendencia = self.columnas = None
        self.error_modelos = None
        try:
            ruta = Path(ruta_modelos)
            self.columnas = joblib.load(ruta / "columnas_caracteristicas.joblib")
            self.modelo_estado = _cargar(ruta / "estado_sklearn.joblib")
            self.modelo_tendencia = _cargar(ruta / "tendencia_sklearn.joblib")
            self.modo = "modelo"
        except Exception as e:  # modelos ausentes o incompatibles
            self.error_modelos = f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------------ API
    def diagnosticar(self, especie, historial):
        """historial: lista de dicts ordenada por fecha; el último es el reporte de hoy.

        Cada dict: fecha (date), dias_desde_siembra y los 7 campos del reporte.
        """
        t0 = time.perf_counter()
        if not historial:
            raise ValueError("Se necesita al menos un reporte.")
        historial = list(historial)[-MAX_HISTORIAL:]
        df = pd.DataFrame([{
            "planta_id": 0, "especie": especie, "dia": h["fecha"].toordinal(),
            "dias_desde_siembra": h["dias_desde_siembra"], **{c: h[c] for c in CAMPOS},
        } for h in historial])
        X, d = construir_caracteristicas(df, self.kb)
        fila_d, fila_x = d.iloc[[-1]], X.iloc[[-1]]
        hoy = {c: historial[-1][c] for c in CAMPOS}

        indice = int(fila_d["idx_obs"].iloc[0])
        estado_reglas = estado_desde_indice(indice, self.kb)
        reglas = reglas_activas(hoy, especie, self.kb)

        if self.modo == "modelo":
            fila_x = fila_x[self.columnas]
            estado, p_est = self._predecir(self.modelo_estado, fila_x)
            tendencia, p_ten = self._predecir(self.modelo_tendencia, fila_x)
        else:
            estado, p_est = estado_reglas, None
            tendencia, p_ten = str(tendencia_reglas(fila_d)[0]), None

        n = len(historial)
        return {
            "estado": estado,
            "probabilidades_estado": p_est,
            "tendencia_3_dias": tendencia,
            "probabilidades_tendencia": p_ten,
            "indice_estres": indice,
            "estado_reglas": estado_reglas,
            "coincide_con_reglas": estado == estado_reglas,
            "modo": self.modo,
            "dias_de_historial": n,
            "aviso_historial": None if n >= 4 else
                "Hay pocos reportes previos (menos de 4): la tendencia es poco confiable.",
            "causas_probables": [
                {"id": r["id"], "causa": r["causa_probable"], "explicacion": r["explicacion"]}
                for r in reglas],
            "acciones": self._acciones(reglas, estado),
            "tiempo_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    # ------------------------------------------------------------------ internos
    @staticmethod
    def _predecir(modelo, fila_x):
        probs = modelo.predict_proba(fila_x)[0]
        i = int(np.argmax(probs))
        return str(modelo.classes_[i]), {str(c): round(float(p), 3) for c, p in zip(modelo.classes_, probs)}

    @staticmethod
    def _acciones(reglas, estado):
        acciones = []
        for r in reglas:
            for a in r["acciones"]:
                if a not in acciones:
                    acciones.append(a)
        if not acciones:
            acciones = (["Mantener el cuidado actual y seguir reportando cada día."]
                        if estado == "Saludable" else
                        ["Revisar de nuevo mañana; ninguna regla específica se activó hoy."])
        return acciones
