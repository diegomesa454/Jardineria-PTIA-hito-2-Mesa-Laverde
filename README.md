# Jardineria

Proyecto del curso PTIA (Escuela Colombiana de Ingeniería Julio Garavito) — Grupo 02.

Sistema híbrido (base de conocimiento + aprendizaje automático) que, a partir de un reporte
diario breve, estima el estado de una planta de autocultivo, anticipa su tendencia a 3 días
y recomienda cuidados con explicación.

## Estructura
| Carpeta | Contenido | Sección del documento |
|---|---|---|
| `docs/` | Documento del Hito 2 (PDF) | — |
| `knowledge/` | Base de conocimiento por especie (YAML) | 6.2, 6.4 |
| `simulator/` | Simulador de balance hídrico y estrés; genera el dataset | 6.5 |
| `notebooks/` | Entrenamiento y comparación de modelos | 6.5 |
| `models/` | Modelos entrenados | 6.5 |
| `backend/` | API (FastAPI) — Hito 3 | 6.4 |
| `frontend/` | Prototipo de interfaz (HTML) | 6.6 |
| `data/` | Datasets generados | 6.5 |

## Estado (Hito 2)
- [x] Prototipo de interfaz navegable
- [x] Base de conocimiento (3 especies): ver knowledge/
- [ ] Simulador y dataset
- [ ] Modelo base (reglas vs. Random Forest)
- [ ] Backend y MVP (Hito 3)

## Uso
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
