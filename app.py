import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(title="AuraTube API", version="6.3.0")

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
    with open(COOKIE_FILE, 'r') as f:
        content = f.read()
        if "youtube.com" in content and "Netscape" in content:
            print(f"✅ COOKIES VÁLIDAS: {COOKIE_FILE} ({len(content)} bytes)")
        else:
            print(f"⚠️ COOKIES INVÁLIDAS")
            HAS_COOKIES = False
else:
    print(f"❌ No se encontró archivo cookies.txt")

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
        "service": "AuraTube API",
        "version": "6.3.0",
        "cookies_available": HAS_COOKIES,
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
        "version": "6.3.0",
        "cookies_available": HAS_COOKIES,
        "ffmpeg_available": os.path.exists(FFMPEG_PATH)
    }

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    if not HAS_COOKIES:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "❌ No hay cookies disponibles"}
        )
    
    try:
        print(f"🔍 Obteniendo info de: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': COOKIE_FILE,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": "No se pudo obtener información"}
                )
            
            formats = []
            for f in info.get('formats', [])[:10]:
                formats.append({
                    "format_id": f.get('format_id'),
                    "ext": f.get('ext'),
                    "resolution": f.get('resolution', 'N/A'),
                    "filesize": f.get('filesize', 0),
                    "format_note": f.get('format_note', '')
                })
            
            return {
                "success": True,
                "title": info.get('title', 'Sin título'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', 'Desconocido'),
                "view_count": info.get('view_count', 0),
                "formats": formats
            }
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error en /info: {error_msg}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": error_msg}
        )

@app.get("/download")
def download(
    url: str = Query(..., description="URL de YouTube"),
    mode: str = Query("audio", description="audio o video"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not HAS_COOKIES:
        raise HTTPException(
            status_code=403,
            detail="❌ No hay cookies disponibles"
        )
    
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"⬇️ Descargando: {url} | Modo: {mode}")

    # Configuración BASE
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': COOKIE_FILE,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
            }
        },
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
    }

    if mode == "video":
        # USAR FORMATO GENÉRICO - SIEMPRE DISPONIBLE
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                
                # Buscar archivo descargado
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
            error_msg = str(e)
            print(f"❌ Error en video: {error_msg}")
            
            # INTENTAR CON FORMATO AÚN MÁS GENÉRICO
            if "Requested format is not available" in error_msg:
                try:
                    print("🔄 Intentando con formato 'best'...")
                    ydl_opts['format'] = 'best'
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
                                filename=filename
                            )
                except Exception as e2:
                    print(f"❌ Falló el fallback: {e2}")
                    error_msg = str(e2)
            
            raise HTTPException(status_code=500, detail=error_msg)
    
    else:  # audio
        # USAR FORMATO GENÉRICO DE AUDIO
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
            error_msg = str(e)
            print(f"❌ Error en audio: {error_msg}")
            
            # INTENTAR CON FORMATO ALTERNATIVO
            if "Requested format is not available" in error_msg:
                try:
                    print("🔄 Intentando con formato alternativo...")
                    ydl_opts['format'] = 'bestaudio'
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
                except Exception as e2:
                    print(f"❌ Falló el fallback: {e2}")
                    error_msg = str(e2)
            
            raise HTTPException(status_code=500, detail=error_msg)
