import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Obtener la ruta del binario estático de FFmpeg integrado en imageio-ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API (Render)",
    description="API privada y gratuita de descarga de música (MP3) y video (MP4) basada en yt-dlp y FFmpeg.",
    version="1.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/auratube"
os.makedirs(TEMP_DIR, exist_ok=True)

# Función para borrar archivos temporales después de enviarlos al cliente
def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo temporal eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar archivo temporal: {e}")

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AuraTube API - Render</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;800&display=swap" rel="stylesheet">
        <style>
            body {
                background: #080911;
                color: #f8fafc;
                font-family: 'Outfit', sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: rgba(15, 17, 34, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                padding: 40px;
                border-radius: 24px;
                text-align: center;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
                max-width: 500px;
            }
            h1 {
                background: linear-gradient(135deg, #06b6d4 0%, #a855f7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
                font-size: 2.5rem;
            }
            p { color: #94a3b8; line-height: 1.6; }
            .badge {
                display: inline-block;
                background: rgba(16, 185, 129, 0.15);
                color: #10b981;
                border: 1px solid rgba(16, 185, 129, 0.3);
                padding: 6px 16px;
                border-radius: 100px;
                font-weight: bold;
                font-size: 0.85rem;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">● API EN LÍNEA (RENDER)</div>
            <h1>AuraTube API</h1>
            <p>Servidor privado de descargas de YouTube ejecutándose en Render. Conéctalo ingresando la URL de este servicio en la configuración de AuraTube.</p>
        </div>
    </body>
    </html>
    """

@app.get("/download")
def download(
    url: str = Query(..., description="URL de YouTube a descargar"),
    mode: str = Query("audio", description="Modo de descarga: 'audio' para MP3 o 'video' para MP4"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"Descargando en Render: {url} | Modo: {mode}")

    # Configuración de bypass antibot de YouTube
    extractor_args = {
        'youtube': {
            'player_client': ['ios', 'mweb']
        }
    }

    # Verificar si existe un archivo cookies.txt en el directorio para autenticar
    cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None

    if mode == "video":
        # CORRECCIÓN DE FORMATO:
        # Descarga el mejor video y el mejor audio disponibles y los une en un archivo MP4 final usando FFmpeg.
        # Esto previene errores de "Requested format is not available" cuando no hay un MP4 combinado pregenerado por YouTube.
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,  # Usar binario de FFmpeg integrado
            'extractor_args': extractor_args,
            'quiet': True,
            'no_warnings': True,
        }
        
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print("Usando archivo cookies.txt para autenticación en video.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                # Como combinamos formatos, aseguramos que la extensión sea .mp4
                base, _ = os.path.splitext(filepath)
                mp4_filepath = base + ".mp4"
                
                # Si el merge de ffmpeg cambió el nombre final del archivo de salida
                if not os.path.exists(mp4_filepath) and os.path.exists(filepath):
                    mp4_filepath = filepath
                
                filename = os.path.basename(mp4_filepath)
                
                background_tasks.add_task(clean_temp_file, mp4_filepath)
                background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                
                return FileResponse(
                    path=mp4_filepath,
                    media_type="video/mp4",
                    filename=filename,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Error en video Render: {str(e)}")
            
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,  # Usar binario de FFmpeg integrado
            'extractor_args': extractor_args,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print("Usando archivo cookies.txt para autenticación en audio.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                base, _ = os.path.splitext(filepath)
                mp3_filepath = base + ".mp3"
                filename = os.path.basename(mp3_filepath)
                
                if not os.path.exists(mp3_filepath):
                    raise Exception("Fallo en la conversión a MP3 por FFmpeg.")
                
                background_tasks.add_task(clean_temp_file, mp3_filepath)
                background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                
                return FileResponse(
                    path=mp3_filepath,
                    media_type="audio/mpeg",
                    filename=filename,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Error en conversión Render: {str(e)}")
