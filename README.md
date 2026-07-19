# AuraTube API - Render Deployment

Este repositorio contiene el backend de conversión (MP3 y MP4) para AuraTube, listo para ser desplegado de forma gratuita en **Render.com**.

## Archivos incluidos:
- `app.py`: Servidor API en Python usando FastAPI e `imageio-ffmpeg` integrado para la codificación.
- `requirements.txt`: Dependencias del entorno de Python.

## Pasos para desplegar en Render de forma gratuita:

1. **Crear repositorio en GitHub**:
   - Crea un repositorio nuevo (público o privado) en tu GitHub.
   - Sube estos dos archivos (`app.py` y `requirements.txt`) a la rama principal (usualmente `main`).

2. **Crear servicio en Render**:
   - Inicia sesión o regístrate en [Render.com](https://render.com) (puedes iniciar sesión con tu cuenta de GitHub). **Es completamente gratis y no requiere ingresar tarjeta de crédito.**
   - Haz clic en el botón azul **"New +"** arriba a la derecha y selecciona **"Web Service"**.
   - Conecta tu cuenta de GitHub y selecciona el repositorio que acabas de crear.

3. **Configurar el Web Service**:
   - **Name**: `auratube-api` (o el nombre que prefieras).
   - **Region**: Selecciona la más cercana (por ejemplo, *Oregon* o *Frankfurt*).
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Selecciona **"Free"** (Costo: $0 USD/mes).

4. **Desplegar**:
   - Haz clic en **"Deploy Web Service"** al final de la página.
   - Render comenzará a construir y levantar la aplicación. Al finalizar, verás que el estado cambia a **"Live"** y te proporcionará una URL pública (ejemplo: `https://auratube-api-xxxx.onrender.com`).

5. **Conectar con AuraTube**:
   - Copia esa URL pública de Render.
   - Ve a la interfaz web de AuraTube (`index.html`), haz clic en el icono de **Ajustes** (engranaje) arriba a la derecha, activa la casilla **"Activar API Privada"** e ingresa la URL de tu API en Render.
   - ¡Listo! Las descargas directas a tu PC sin publicidad comenzarán a procesarse a través de tu servidor en Render.
