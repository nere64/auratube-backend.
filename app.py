import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import re

# Obtener la ruta del binario estático de FFmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API",
    description="API de descarga de YouTube para Spaceship",
    version="3.1.0"
)

# CORS para Spaceship
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/auratube"
os.makedirs(TEMP_DIR, exist_ok=True)

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AuraTube API</title>
        <meta charset="UTF-8">
        <style>
            body {
                background: #0a0a0f;
                color: #fff;
                font-family: system-ui, -apple-system, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .container {
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.03);
                border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.06);
                max-width: 500px;
            }
            h1 {
                background: linear-gradient(135deg, #06b6d4, #a855f7);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.5rem;
            }
            .status {
                color: #10b981;
                font-size: 0.9rem;
                margin: 10px 0;
            }
            .badge {
                display: inline-block;
                background: rgba(16,185,129,0.15);
                color: #10b981;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.8rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="badge">● ONLINE</div>
            <h1>AuraTube API</h1>
            <p style="color: #94a3b8;">Servidor activo para Spaceship</p>
            <div class="status">✅ Conectado a Render</div>
        </div>
    </body>
    </html>
    """

@app.get("/download")
def download(
    url: str = Query(..., description="URL de YouTube"),
    mode: str = Query("audio", description="audio o video"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"Descargando: {url} | Modo: {mode}")

    # Configuración con User-Agent real
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'retries': 10,
        'fragment_retries': 10,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    # Usar cookies si existen
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
        print("Usando cookies.txt")

    if mode == "video":
        ydl_opts.update({
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
        })
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                if os.path.exists(filepath):
                    filename = os.path.basename(filepath)
                    background_tasks.add_task(clean_temp_file, filepath)
                    background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                    
                    return FileResponse(
                        path=filepath,
                        media_type="video/mp4",
                        filename=filename,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                    )
                else:
                    # Buscar cualquier archivo
                    files = os.listdir(download_path)
                    if files:
                        filepath = os.path.join(download_path, files[0])
                        filename = os.path.basename(filepath)
                        background_tasks.add_task(clean_temp_file, filepath)
                        background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                        return FileResponse(
                            path=filepath,
                            media_type="video/mp4",
                            filename=filename,
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                        )
                    raise Exception("No se encontró el archivo")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    else:  # audio
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                # Buscar MP3
                mp3_file = os.path.splitext(filepath)[0] + ".mp3"
                if os.path.exists(mp3_file):
                    filename = os.path.basename(mp3_file)
                    background_tasks.add_task(clean_temp_file, mp3_file)
                    background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                    
                    return FileResponse(
                        path=mp3_file,
                        media_type="audio/mpeg",
                        filename=filename,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                    )
                else:
                    # Buscar cualquier MP3
                    files = [f for f in os.listdir(download_path) if f.endswith('.mp3')]
                    if files:
                        filepath = os.path.join(download_path, files[0])
                        filename = os.path.basename(filepath)
                        background_tasks.add_task(clean_temp_file, filepath)
                        background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                        return FileResponse(
                            path=filepath,
                            media_type="audio/mpeg",
                            filename=filename,
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                        )
                    raise Exception("No se encontró el MP3")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    """Obtiene información del video sin descargar"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Formatear respuesta para Spaceship
            return {
                "success": True,
                "title": info.get('title', ''),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', ''),
                "view_count": info.get('view_count', 0),
                "formats": [
                    {
                        "format_id": f.get('format_id'),
                        "ext": f.get('ext'),
                        "resolution": f.get('resolution', 'N/A'),
                        "filesize": f.get('filesize', 0),
                        "format_note": f.get('format_note', '')
                    }
                    for f in info.get('formats', [])
                    if f.get('ext') in ['mp4', 'm4a', 'webm']
                ]
            }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/health")
def health():
    return {"status": "healthy", "version": "3.1.0"}
