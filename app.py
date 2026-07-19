import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(title="AuraTube API", version="7.0.0")

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
    print(f"✅ Cookies encontradas")
else:
    print(f"❌ No se encontró cookies.txt")

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

def get_available_formats(url):
    """Obtiene TODOS los formatos disponibles de un video"""
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
        return info.get('formats', [])

def select_best_format(formats, mode):
    """Selecciona el MEJOR formato disponible automáticamente"""
    
    if mode == 'audio':
        # Buscar audio en mp4 o m4a (mejor calidad)
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                if f.get('ext') in ['m4a', 'mp4']:
                    return f.get('format_id')
        
        # Si no hay, buscar cualquier audio
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('format_id')
        
        # Último recurso: cualquier formato con audio
        for f in formats:
            if f.get('acodec') != 'none':
                return f.get('format_id')
    
    else:  # video
        # Buscar MP4 con audio y video
        for f in formats:
            if (f.get('ext') == 'mp4' and 
                f.get('vcodec') != 'none' and 
                f.get('acodec') != 'none'):
                return f.get('format_id')
        
        # Si no hay, buscar cualquier video con audio
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                return f.get('format_id')
        
        # Último recurso: cualquier video
        for f in formats:
            if f.get('vcodec') != 'none':
                return f.get('format_id')
    
    return None

@app.get("/")
def index():
    return {
        "service": "AuraTube API",
        "version": "7.0.0",
        "cookies_available": HAS_COOKIES,
        "status": "online"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "7.0.0",
        "cookies_available": HAS_COOKIES,
        "ffmpeg_available": os.path.exists(FFMPEG_PATH)
    }

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    """Obtiene información del video y sus formatos disponibles"""
    try:
        formats = get_available_formats(url)
        
        if not formats:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "No se encontraron formatos para este video"}
            )
        
        # Seleccionar mejores formatos automáticamente
        best_audio = select_best_format(formats, 'audio')
        best_video = select_best_format(formats, 'video')
        
        # Mostrar primeros 10 formatos para debug
        format_list = []
        for f in formats[:10]:
            format_list.append({
                "format_id": f.get('format_id'),
                "ext": f.get('ext'),
                "resolution": f.get('resolution', 'N/A'),
                "vcodec": f.get('vcodec', 'none'),
                "acodec": f.get('acodec', 'none'),
                "filesize": f.get('filesize', 0)
            })
        
        return {
            "success": True,
            "title": "Video encontrado",
            "best_audio_format": best_audio,
            "best_video_format": best_video,
            "available_formats": format_list,
            "total_formats": len(formats)
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
    if not HAS_COOKIES:
        raise HTTPException(
            status_code=403,
            detail="❌ No hay cookies disponibles"
        )
    
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"⬇️ Descargando: {url} | Modo: {mode}")

    # PASO 1: OBTENER FORMATOS DISPONIBLES
    try:
        formats = get_available_formats(url)
        if not formats:
            raise Exception("No se encontraron formatos para este video")
        
        # PASO 2: SELECCIONAR EL MEJOR FORMATO AUTOMÁTICAMENTE
        best_format = select_best_format(formats, mode)
        
        if not best_format:
            raise Exception(f"No se encontró un formato adecuado para {mode}")
        
        print(f"✅ Formato seleccionado: {best_format}")
        
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Error al analizar formatos: {str(e)}")

    # PASO 3: DESCARGAR CON EL FORMATO SELECCIONADO
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'retries': 10,
        'fragment_retries': 10,
        'cookiefile': COOKIE_FILE,
        'format': best_format,  # Usar el formato seleccionado automáticamente
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

    # Si es audio, agregar postprocesador
    if mode == "audio":
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Buscar el archivo descargado
            downloaded_files = os.listdir(download_path)
            if not downloaded_files:
                raise Exception("No se descargó ningún archivo")
            
            # Buscar el archivo correcto
            if mode == "audio":
                # Buscar MP3
                mp3_files = [f for f in downloaded_files if f.endswith('.mp3')]
                if mp3_files:
                    filepath = os.path.join(download_path, mp3_files[0])
                else:
                    filepath = os.path.join(download_path, downloaded_files[0])
            else:
                # Buscar MP4
                mp4_files = [f for f in downloaded_files if f.endswith('.mp4')]
                if mp4_files:
                    filepath = os.path.join(download_path, mp4_files[0])
                else:
                    filepath = os.path.join(download_path, downloaded_files[0])
            
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
        print(f"❌ Error en descarga: {error_msg}")
        
        # Si falla, intentar con formato 'best' genérico como último recurso
        if "Requested format is not available" in error_msg:
            try:
                print("🔄 Intentando con formato 'best' como último recurso...")
                ydl_opts['format'] = 'best' if mode == "video" else 'bestaudio'
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded_files = os.listdir(download_path)
                    if downloaded_files:
                        filepath = os.path.join(download_path, downloaded_files[0])
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
