import os, uuid, shutil, yt_dlp, imageio_ffmpeg
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
app = FastAPI(title="AuraTube API", version="7.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

TEMP_DIR = "/tmp/auratube"
os.makedirs(TEMP_DIR, exist_ok=True)

COOKIE_FILE = "cookies.txt"
HAS_COOKIES = os.path.exists(COOKIE_FILE)
print(f"✅ Cookies disponibles: {HAS_COOKIES}")

def clean_temp_file(filepath):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"Archivo eliminado: {filepath}")
        except Exception as e:
            print(f"Error al eliminar: {e}")

@app.get("/")
def index():
    return {"service": "AuraTube API", "version": "7.1.0", "cookies_available": HAS_COOKIES}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "7.1.0", "cookies_available": HAS_COOKIES, "ffmpeg": os.path.exists(FFMPEG_PATH)}

@app.get("/info")
def video_info(url: str = Query(...)):
    if not HAS_COOKIES:
        return JSONResponse(status_code=403, content={"success": False, "error": "❌ Sube cookies.txt a Render"})
    try:
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'cookiefile': COOKIE_FILE,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "success": True,
                "title": info.get('title'),
                "duration": info.get('duration'),
                "thumbnail": info.get('thumbnail'),
                "uploader": info.get('uploader')
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/download")
def download(url: str = Query(...), mode: str = Query("audio"), background_tasks: BackgroundTasks = BackgroundTasks()):
    if not HAS_COOKIES:
        raise HTTPException(status_code=403, detail="❌ Sube cookies.txt a Render")
    
    download_id = str(uuid.uuid4())
    download_path = os.path.join(TEMP_DIR, download_id)
    os.makedirs(download_path, exist_ok=True)
    
    print(f"⬇️ Descargando: {url} | Modo: {mode}")
    
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'ignoreerrors': False,
        'retries': 10, 'cookiefile': COOKIE_FILE,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
    }
    
    if mode == "video":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'  # Formato genérico que siempre existe
    else:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = os.listdir(download_path)
            if not files:
                raise Exception("No se descargó ningún archivo")
            filepath = os.path.join(download_path, files[0])
            media_type = "audio/mpeg" if mode == "audio" else "video/mp4"
            background_tasks.add_task(clean_temp_file, filepath)
            background_tasks.add_task(shutil.rmtree, download_path, ignore_errors=True)
            return FileResponse(path=filepath, media_type=media_type, filename=files[0])
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))
