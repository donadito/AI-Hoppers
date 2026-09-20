# Proyecto Hoppers

## Requisitos

- Python 3.10 al menos.
- Jupyter Notebook o VS Code con soporte para notebooks.
- La dependencia en requirements.txt, que solo es pygames.

## Instalación

Desde una terminal ubicada en esta carpeta:

```bash
python -m pip install -r requirements.txt
```

En Windows también puede usarse:

```bash
py -m pip install -r requirements.txt
```

pygame-ce se importa en Python mediante import pygame.

## Ejecución

1. Abrir Proyecto1_Hoppers_Final.ipynb.
2. Reiniciar el kernel.
3. Ejecutar Run All.
4. Ejecutar manualmente una de las llamadas de la sección final del notebook.

Las llamadas interactivas están comentadas para que **Run All** no abra ventanas ni solicite entradas.

## Archivos visuales

BYD.png y PRADO.png deben permanecer en la misma carpeta que el notebook.

## Modos disponibles

- Humano contra agente.
- Agente contra agente.
- Controlador textual para pruebas.

Durante las pruebas puede utilizarse `time_limit=1`. Para la configuración solicitada en el proyecto debe utilizarse `time_limit=30`.
