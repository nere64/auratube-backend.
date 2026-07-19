import os
import uuid
import shutil
import yt_dlp
import imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI(
    title="AuraTube API (Render)",
    description="API de descarga de YouTube para Spaceship",
    version="4.0.0"
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

# Verificar cookies al inicio
COOKIE_FILE = "cookies.txt"
HAS_COOKIES = os.path.exists(COOKIE_FILE)

if HAS_COOKIES:
    print(f"✅ Cookies encontradas: {COOKIE_FILE}")
    # Mostrar primeras líneas para debug
    with open(COOKIE_FILE, 'r') as f:
        lines = f.readlines()[:5]
        print("Primeras líneas de cookies:")
        for line in lines:
            print(line.strip())
else:
    print("⚠️ No se encontró archivo cookies.txt")

def clean_temp_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

@app.get("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>AuraTube API</title></head>
    <body style="background:#0a0a0f;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;">
        <div style="text-align:center;">
            <h1 style="background:linear-gradient(135deg,#06b6d4,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">AuraTube API</h1>
            <p style="color:#94a3b8;">Servidor activo para Spaceship</p>
            <p style="color:#10b981;">✅ Cookies: {}</p>
        </div>
    </body>
    </html>
    """.format("Activas" if HAS_COOKIES else "No disponibles")

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

    # Configuración BASE con headers de navegador real
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
            'Sec-Fetch-Mode': 'navigate',
        }
    }

    # AÑADIR COOKIES si existen
    if HAS_COOKIES:
        ydl_opts['cookiefile'] = COOKIE_FILE
        print("✅ Usando cookies.txt para autenticación")
    else:
        print("⚠️ Descargando sin cookies (puede fallar en videos restringidos)")

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
                        filename=filename
                    )
                else:
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
            if "Sign in to confirm" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail="YouTube requiere autenticación. El archivo cookies.txt no es válido o ha expirado. Regenera las cookies siguiendo la guía."
                )
            raise HTTPException(status_code=500, detail=error_msg)
    
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
            if "Sign in to confirm" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail="YouTube requiere autenticación. El archivo cookies.txt no es válido o ha expirado. Regenera las cookies siguiendo la guía."
                )
            raise HTTPException(status_code=500, detail=error_msg)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "4.0.0",
        "cookies_available": HAS_COOKIES
    }
