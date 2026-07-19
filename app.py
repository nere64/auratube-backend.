import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API",
    description="API de descarga de YouTube para Spaceship",
    version="6.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/auratube"
os.makedirs(TEMP_DIR, exist_ok=True)

COOKIE_FILE = "cookies.txt"
HAS_COOKIES = os.path.exists(COOKIE_FILE)

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "AuraTube API",
        "version": "6.0.0",
        "endpoints": {
            "/health": "Estado del servidor",
            "/info": "Información del video",
            "/download": "Descargar audio/video"
        }
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "6.0.0",
        "cookies_available": HAS_COOKIES,
        "ffmpeg_available": os.path.exists(FFMPEG_PATH)
    }

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    """Obtiene información del video sin descargar"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                }
            }
        }
        
        if HAS_COOKIES:
            ydl_opts['cookiefile'] = COOKIE_FILE
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "No se pudo obtener información"}
                )
            
            return {
                "success": True,
                "title": info.get('title', 'Sin título'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', 'Desconocido'),
                "view_count": info.get('view_count', 0),
                "formats": [
                    {
                        "format_id": f.get('format_id'),
                        "ext": f.get('ext'),
                        "resolution": f.get('resolution', 'N/A'),
                        "filesize": f.get('filesize', 0),
                    }
                    for f in info.get('formats', [])[:5]
                ]
            }
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

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

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'retries': 10,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'skip': ['hls', 'dash'],
            }
        },
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
    }

    if HAS_COOKIES:
        ydl_opts['cookiefile'] = COOKIE_FILE

    if mode == "video":
        ydl_opts['format'] = 'best[height<=720][ext=mp4]/best[ext=mp4]/best'
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                # Buscar el archivo descargado
                if os.path.exists(filepath):
                    filename = os.path.basename(filepath)
                    background_tasks.add_task(clean_temp_file, filepath)
                    background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                    return FileResponse(
                        path=filepath,
                        media_type="video/mp4",
                        filename=filename
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
                            filename=filename
                        )
                    raise Exception("No se encontró el archivo")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    else:  # audio
        ydl_opts.update({
            'format': 'bestaudio/best',
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
                
                mp3_file = os.path.splitext(filepath)[0] + ".mp3"
                if os.path.exists(mp3_file):
                    filename = os.path.basename(mp3_file)
                    background_tasks.add_task(clean_temp_file, mp3_file)
                    background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                    return FileResponse(
                        path=mp3_file,
                        media_type="audio/mpeg",
                        filename=filename
                    )
                else:
                    files = [f for f in os.listdir(download_path) if f.endswith('.mp3')]
                    if files:
                        filepath = os.path.join(download_path, files[0])
                        filename = os.path.basename(filepath)
                        background_tasks.add_task(clean_temp_file, filepath)
                        background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                        return FileResponse(
                            path=filepath,
                            media_type="audio/mpeg",
                            filename=filename
                        )
                    raise Exception("No se encontró el MP3")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            raise HTTPException(status_code=500, detail=str(e))
