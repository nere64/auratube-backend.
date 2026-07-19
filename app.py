import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Obtener la ruta del binario estático de FFmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API",
    description="API de descarga de YouTube para Spaceship",
    version="5.0.0"
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

# Verificar cookies
COOKIE_FILE = "cookies.txt"
HAS_COOKIES = os.path.exists(COOKIE_FILE)

if HAS_COOKIES:
    print(f"✅ Cookies encontradas: {COOKIE_FILE}")
else:
    print("⚠️ No se encontró archivo cookies.txt")

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

def get_best_format(formats, mode='audio'):
    """Selecciona el mejor formato disponible automáticamente"""
    if mode == 'audio':
        # Buscar mejor audio
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                # Priorizar m4a y mp4 con mejor calidad
                if f.get('ext') in ['m4a', 'mp4']:
                    return f.get('format_id')
        # Fallback: cualquier audio
        for f in formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                return f.get('format_id')
        return None
    else:  # video
        # Buscar mejor video con audio incluido
        for f in formats:
            if (f.get('ext') == 'mp4' and 
                f.get('vcodec') != 'none' and 
                f.get('acodec') != 'none' and
                'h264' in f.get('vcodec', '').lower()):
                return f.get('format_id')
        # Fallback: cualquier mp4 con audio
        for f in formats:
            if (f.get('ext') == 'mp4' and 
                f.get('vcodec') != 'none' and 
                f.get('acodec') != 'none'):
                return f.get('format_id')
        # Último recurso: cualquier formato
        for f in formats:
            if f.get('vcodec') != 'none':
                return f.get('format_id')
        return None

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

@app.get("/info")
def video_info(url: str = Query(..., description="URL de YouTube")):
    """Obtiene información del video sin descargar"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        if HAS_COOKIES:
            ydl_opts['cookiefile'] = COOKIE_FILE
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
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
                        "format_note": f.get('format_note', ''),
                        "vcodec": f.get('vcodec', 'none'),
                        "acodec": f.get('acodec', 'none')
                    }
                    for f in info.get('formats', [])
                    if f.get('ext') in ['mp4', 'm4a', 'webm', 'mp3']
                ]
            }
    except Exception as e:
        error_msg = str(e)
        print(f"Error en /info: {error_msg}")
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
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"Descargando: {url} | Modo: {mode}")

    # PRIMERO: Obtener formatos disponibles
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            if not formats:
                raise HTTPException(status_code=400, detail="No se encontraron formatos disponibles")
            
            # Seleccionar el mejor formato automáticamente
            best_format_id = get_best_format(formats, mode)
            
            if not best_format_id:
                raise HTTPException(status_code=400, detail="No se encontró un formato adecuado")
            
            print(f"✅ Formato seleccionado: {best_format_id}")
            
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        error_msg = str(e)
        print(f"Error obteniendo formatos: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Error: {error_msg}")

    # Configuración con el formato seleccionado
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'retries': 10,
        'fragment_retries': 10,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }

    if HAS_COOKIES:
        ydl_opts['cookiefile'] = COOKIE_FILE
        print("✅ Usando cookies.txt")

    if mode == "video":
        ydl_opts.update({
            'format': best_format_id,  # Usar el formato específico
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
        })
        
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
                    # Buscar cualquier archivo en el directorio
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
                    raise Exception("No se encontró el archivo descargado")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            error_msg = str(e)
            print(f"Error en video: {error_msg}")
            
            # Intentar con formato alternativo
            if "Requested format is not available" in error_msg:
                try:
                    # Usar formato genérico como fallback
                    fallback_opts = ydl_opts.copy()
                    fallback_opts['format'] = 'best[ext=mp4]/best'
                    
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
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
                    error_msg = str(e2)
            
            raise HTTPException(status_code=500, detail=error_msg)
    
    else:  # audio
        ydl_opts.update({
            'format': best_format_id,  # Usar el formato específico
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
                        filename=filename
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
                            filename=filename
                        )
                    raise Exception("No se encontró el archivo MP3")
                    
        except Exception as e:
            shutil.rmtree(download_path, ignore_errors=True)
            error_msg = str(e)
            print(f"Error en audio: {error_msg}")
            
            # Intentar con formato genérico como fallback
            if "Requested format is not available" in error_msg:
                try:
                    fallback_opts = ydl_opts.copy()
                    fallback_opts['format'] = 'bestaudio/best'
                    
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
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
                    error_msg = str(e2)
            
            raise HTTPException(status_code=500, detail=error_msg)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "5.0.0",
        "cookies_available": HAS_COOKIES,
        "ffmpeg_available": os.path.exists(FFMPEG_PATH)
    }
