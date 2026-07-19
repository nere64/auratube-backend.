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
    version="2.0.0"
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
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: #080911;
                color: #f8fafc;
                font-family: 'Outfit', sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }
            .card {
                background: rgba(15, 17, 34, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                padding: 40px;
                border-radius: 24px;
                text-align: center;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 100%;
                backdrop-filter: blur(10px);
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            h1 {
                background: linear-gradient(135deg, #06b6d4 0%, #a855f7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
                font-size: 2.5rem;
                letter-spacing: -1px;
            }
            .subtitle {
                color: #94a3b8;
                line-height: 1.6;
                margin-bottom: 20px;
                font-size: 1rem;
            }
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
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 0.7; }
                50% { opacity: 1; }
                100% { opacity: 0.7; }
            }
            .features {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            .feature-item {
                background: rgba(255, 255, 255, 0.03);
                padding: 10px 15px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                font-size: 0.85rem;
                color: #cbd5e1;
            }
            .feature-item span {
                color: #06b6d4;
                font-weight: bold;
            }
            .version {
                color: #475569;
                font-size: 0.75rem;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">● API EN LÍNEA (RENDER)</div>
            <h1>AuraTube API</h1>
            <p class="subtitle">Servidor privado de descargas de YouTube ejecutándose en Render. Conéctalo ingresando la URL de este servicio en la configuración de AuraTube.</p>
            <div class="features">
                <div class="feature-item">🎵 <span>MP3</span> 192kbps</div>
                <div class="feature-item">🎬 <span>MP4</span> HD</div>
                <div class="feature-item">⚡ <span>Rápido</span></div>
            </div>
            <div class="version">v2.0.0 • FFmpeg integrado</div>
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
    
    print(f"Descargando en Render: {url} | Modo: {mode} | ID: {download_id}")

    # Configuración de bypass antibot de YouTube mejorada
    extractor_args = {
        'youtube': {
            'player_client': ['ios', 'mweb', 'android'],
            'skip': ['dash'],  # Saltar DASH para evitar problemas
        }
    }

    # Verificar si existe un archivo cookies.txt en el directorio para autenticar
    cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None

    if mode == "video":
        # Configuración mejorada para video con múltiples fallbacks
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'extractor_args': extractor_args,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'retries': 5,
            'fragment_retries': 5,
            'skip_download': False,
        }
        
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print("Usando archivo cookies.txt para autenticación en video.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Descargar el video
                info = ydl.extract_info(url, download=True)
                
                # Buscar el archivo descargado
                downloaded_files = os.listdir(download_path)
                if not downloaded_files:
                    raise Exception("No se descargó ningún archivo")
                
                # Buscar archivo MP4
                mp4_files = [f for f in downloaded_files if f.endswith('.mp4')]
                if mp4_files:
                    filepath = os.path.join(download_path, mp4_files[0])
                else:
                    # Usar el primer archivo descargado
                    filepath = os.path.join(download_path, downloaded_files[0])
                
                filename = os.path.basename(filepath)
                
                background_tasks.add_task(clean_temp_file, filepath)
                background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                
                return FileResponse(
                    path=filepath,
                    media_type="video/mp4",
                    filename=filename,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            error_msg = str(e)
            print(f"Error detallado en video: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Error en video Render: {error_msg}")
            
    else:  # Modo audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'extractor_args': extractor_args,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'retries': 5,
            'fragment_retries': 5,
        }
        
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print("Usando archivo cookies.txt para autenticación en audio.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Buscar el archivo MP3
                downloaded_files = os.listdir(download_path)
                mp3_files = [f for f in downloaded_files if f.endswith('.mp3')]
                
                if mp3_files:
                    filepath = os.path.join(download_path, mp3_files[0])
                else:
                    # Si no hay MP3, intentar encontrar el archivo descargado
                    if downloaded_files:
                        filepath = os.path.join(download_path, downloaded_files[0])
                    else:
                        raise Exception("No se encontró el archivo descargado")
                
                filename = os.path.basename(filepath)
                
                background_tasks.add_task(clean_temp_file, filepath)
                background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                
                return FileResponse(
                    path=filepath,
                    media_type="audio/mpeg",
                    filename=filename,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            error_msg = str(e)
            print(f"Error detallado en audio: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Error en conversión Render: {error_msg}")

@app.get("/health")
def health_check():
    """Endpoint para verificar el estado del servidor"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "ffmpeg_available": os.path.exists(FFMPEG_PATH),
        "temp_dir": TEMP_DIR
    }
