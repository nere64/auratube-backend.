import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import json

# Obtener la ruta del binario estático de FFmpeg integrado en imageio-ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API (Render)",
    description="API privada y gratuita de descarga de música (MP3) y video (MP4) basada en yt-dlp y FFmpeg.",
    version="3.0.0"
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

# Función para obtener formato automáticamente
def get_best_format(formats, mode='video'):
    """Obtiene el mejor formato disponible automáticamente"""
    if mode == 'video':
        # Priorizar MP4 con video y audio
        for f in formats:
            if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                return f.get('format_id')
        # Si no hay, buscar solo video
        for f in formats:
            if f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                return f.get('format_id')
        # Último recurso: cualquier formato
        return formats[0].get('format_id') if formats else None
    else:
        # Para audio: buscar mejor audio
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('format_id')
        # Si no hay audio solo, buscar cualquier audio
        for f in formats:
            if f.get('acodec') != 'none':
                return f.get('format_id')
        return None

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
            }
            h1 {
                background: linear-gradient(135deg, #06b6d4 0%, #a855f7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
                font-size: 2.5rem;
            }
            .subtitle {
                color: #94a3b8;
                line-height: 1.6;
                margin-bottom: 20px;
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
            <div class="version">v3.0.0 • Auto-format</div>
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

    # Verificar cookies
    cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None
    
    # PRIMERO: Obtener lista de formatos disponibles
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            if not formats:
                raise HTTPException(status_code=400, detail="No se encontraron formatos disponibles")
            
            # Encontrar el mejor formato automáticamente
            best_format_id = get_best_format(formats, mode)
            
            if not best_format_id:
                raise HTTPException(status_code=400, detail="No se encontró un formato adecuado")
            
            print(f"Formato seleccionado: {best_format_id}")
            
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        error_msg = str(e)
        print(f"Error obteniendo formatos: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Error: {error_msg}")

    if mode == "video":
        # Configuración para video usando el formato encontrado
        ydl_opts = {
            'format': f'{best_format_id}+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'retries': 10,
            'fragment_retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
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
            raise HTTPException(status_code=500, detail=f"Error en video: {error_msg}")
            
    else:  # Modo audio
        # Para audio, usar el formato de audio encontrado
        ydl_opts = {
            'format': best_format_id,
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'retries': 10,
            'fragment_retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
            print("Usando archivo cookies.txt para autenticación en audio.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Descargar y convertir a MP3
                info = ydl.extract_info(url, download=True)
                
                # Buscar archivos en el directorio
                downloaded_files = os.listdir(download_path)
                if not downloaded_files:
                    raise Exception("No se descargó ningún archivo")
                
                # Buscar archivo MP3
                mp3_files = [f for f in downloaded_files if f.endswith('.mp3')]
                if mp3_files:
                    filepath = os.path.join(download_path, mp3_files[0])
                else:
                    # Si no hay MP3, usar el primer archivo
                    filepath = os.path.join(download_path, downloaded_files[0])
                    # Verificar si es un archivo de audio
                    if not filepath.endswith(('.mp3', '.m4a', '.webm', '.opus')):
                        raise Exception("No se encontró un archivo de audio válido")
                
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
            raise HTTPException(status_code=500, detail=f"Error en audio: {error_msg}")

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo temporal eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar archivo temporal: {e}")

@app.get("/health")
def health_check():
    """Endpoint para verificar el estado del servidor"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "ffmpeg_available": os.path.exists(FFMPEG_PATH),
        "ffmpeg_path": FFMPEG_PATH,
        "temp_dir": TEMP_DIR
    }

@app.get("/formats")
def get_formats(url: str = Query(..., description="URL de YouTube")):
    """Endpoint para ver los formatos disponibles de un video"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            result = []
            for f in formats:
                result.append({
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution', 'N/A'),
                    'filesize': f.get('filesize', 'N/A'),
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none')
                })
            
            return {
                "title": info.get('title'),
                "formats": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
