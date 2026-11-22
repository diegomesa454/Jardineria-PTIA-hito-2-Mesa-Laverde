# Backend de JardinerIA (Hito 3)

API REST (FastAPI) + SQLite + interfaz web mínima. Recibe el reporte diario, arma las
características con la ventana de 3 días, predice estado y tendencia (Random Forest) y devuelve
causa probable, acciones y explicación desde la base de conocimiento.

## Ejecutar (PowerShell, desde la raíz del repo)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements-backend.txt
    python -m uvicorn backend.main:app --reload
Abrir http://127.0.0.1:8000 (interfaz) o http://127.0.0.1:8000/docs (documentación interactiva).

Necesita en `models/`: `estado_sklearn.joblib`, `tendencia_sklearn.joblib` y
`columnas_caracteristicas.joblib` (salen de `notebooks/hito3_comparacion_modelos.py`). Si faltan,
el servicio arranca en **modo reglas** (solo base de conocimiento) y lo avisa en `/api/salud`.

## Endpoints
| Método | Ruta | Para qué |
|---|---|---|
| GET | /api/salud | Estado del servicio y modo (`modelo` o `reglas`) |
| POST | /api/plantas | Crear planta (`nombre`, `especie`, `dias_desde_siembra`) |
| GET | /api/plantas | Listar plantas con su último estado |
| DELETE | /api/plantas/{id} | Borrar planta e historial |
| POST | /api/plantas/{id}/reportes | Enviar el reporte de hoy y recibir el diagnóstico |
| GET | /api/plantas/{id}/reportes | Historial de reportes y diagnósticos |
| POST | /api/diagnostico | Diagnóstico sin guardar nada (para probar escenarios) |

## Pruebas
    python -m pytest -q

## Limitaciones conocidas
- El historial se toma por reportes, no por días de calendario: si faltan días, la tendencia se
  calcula con los reportes disponibles (el modelo se entrenó con reportes diarios).
- Con menos de 4 reportes la respuesta incluye `aviso_historial`.
- Los modelos se entrenaron solo con datos simulados (ver distribution shift en el informe).
