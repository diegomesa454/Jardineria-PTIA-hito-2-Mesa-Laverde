# Simulador y motor de reglas

- `motor_reglas.py`: lee `knowledge/` y calcula índice de estrés, estado y reglas activas.
- `simulador.py`: genera plantas virtuales (balance hídrico + salud con inercia + perfiles de jardinero).

## Generar el dataset

```bash
python -m simulator.simulador --plantas 200 --dias 30 --semilla 42 --salida data/dataset_simulado.csv
```

Produce 18.000 filas (3 especies x 200 plantas x 30 días). Distribución del estado:
50 % Saludable, 21 % Atención, 30 % Crítico.

## Cómo se etiqueta

1. Cada día se calcula un reporte **verdadero** (sin ruido) a partir de las variables latentes.
2. Con ese reporte y la base de conocimiento se calcula el **índice de estrés** y el **estado**.
3. La **tendencia** compara el índice de hoy con el de 3 días después (Mejora / Estable / Empeora).
4. Las columnas de entrada del dataset son el reporte **observado**, con ruido de percepción
   (categorías vecinas, error de ±1,5 °C en temperatura y ±1 h en sol). El modelo debe aprender a pesar de ese ruido.
5. La partición entrenamiento / validación / prueba (70/15/15) se hace **por planta**, no por día.

## Limitaciones

Los datos son simulados: las métricas sobre ellos miden coherencia con la base de conocimiento,
no desempeño con plantas reales. Los parámetros de la dinámica (evaporación, daño, recuperación,
ruido) son supuestos del equipo.

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest tests
```
