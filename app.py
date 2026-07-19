import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(title="AuraTube API", version="8.0.0")

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

if HAS_COOKIES:
    print("✅ Cookies disponibles")
else:
    print("⚠️ Sin cookies, se intentará igual")

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

@app.get("/")
def index():
    return {
        "service": "AuraTube API",
        "version": "8.0.0",
        "cookies": HAS_COOKIES,
        "status": "online"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "8.0.0",
        "cookies_available": HAS_COOKIES,
        "ffmpeg_available": os.path.exists(FFMPEG_PATH)
    }

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    """Obtiene información básica del video"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': COOKIE_FILE if HAS_COOKIES else None,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "success": True,
                "title": info.get('title', 'Sin título'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', 'Desconocido')
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

    # Configuración BASE - SIN FORMATOS ESPECÍFICOS
    ydl_opts = {
        'quiet': False,  # Para ver logs en consola
        'no_warnings': False,
        'ignoreerrors': False,
        'retries': 10,
        'fragment_retries': 10,
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
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

    if mode == "video":
        # FORMATO MÁS GENÉRICO POSIBLE
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:  # audio
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Buscar el archivo descargado
            files = os.listdir(download_path)
            if not files:
                raise Exception("No se descargó ningún archivo")
            
            # Para audio, buscar MP3; para video, buscar MP4
            if mode == "audio":
                target_files = [f for f in files if f.endswith('.mp3')]
                if not target_files:
                    # Si no hay MP3, usar el primer archivo
                    target_files = [files[0]]
            else:
                target_files = [f for f in files if f.endswith('.mp4')]
                if not target_files:
                    target_files = [files[0]]
            
            filepath = os.path.join(download_path, target_files[0])
            filename = os.path.basename(filepath)
            media_type = "audio/mpeg" if mode == "audio" else "video/mp4"
            
            background_tasks.add_task(clean_temp_file, filepath)
            background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
            
            return FileResponse(
                path=filepath,
                media_type=media_type,
                filename=filename
            )
            
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        
        # Si el error es por formato, intentar con 'best' a secas
        if "Requested format is not available" in error_msg:
            try:
                print("🔄 Intentando con formato 'best'...")
                ydl_opts['format'] = 'best'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    files = os.listdir(download_path)
                    if files:
                        filepath = os.path.join(download_path, files[0])
                        filename = os.path.basename(filepath)
                        media_type = "audio/mpeg" if mode == "audio" else "video/mp4"
                        background_tasks.add_task(clean_temp_file, filepath)
                        background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
                        return FileResponse(
                            path=filepath,
                            media_type=media_type,
                            filename=filename
                        )
            except Exception as e2:
                error_msg = str(e2)
        
        raise HTTPException(status_code=500, detail=error_msg)
