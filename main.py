from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telethon import TelegramClient
from pyrogram import Client as PyrogramClient
import os
import time
import hashlib

app = FastAPI(title="SQLite Telegram Session API")

# Setup caching directory and expiry time (30 minutes)
CACHE_DIR = "session_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_EXPIRY = 30 * 60 

class SessionRequest(BaseModel):
    api_id: int
    api_hash: str
    bot_token: str
    library: str = "telethon" # Accepts "telethon" or "pyrogram"

@app.post("/generate")
async def generate_session(req: SessionRequest):
    lib = req.library.lower()
    if lib not in ["telethon", "pyrogram"]:
        raise HTTPException(status_code=400, detail="Library must be 'telethon' or 'pyrogram'")

    # Create a unique filename hash based on the bot token AND the library
    hash_str = f"{req.bot_token}_{lib}"
    token_hash = hashlib.md5(hash_str.encode()).hexdigest()
    
    # Path handling: The clients will automatically append ".session"
    session_base_path = os.path.join(CACHE_DIR, token_hash)
    file_path = f"{session_base_path}.session"

    # 1. Check Cache
    if os.path.exists(file_path):
        file_age = time.time() - os.path.getmtime(file_path)
        if file_age < CACHE_EXPIRY:
            return FileResponse(
                path=file_path, 
                filename=f"{lib}_bot.session", 
                media_type="application/octet-stream" # Triggers a binary file download
            )
        else:
            # Delete expired SQLite session file
            os.remove(file_path)

    # 2. Generate New SQLite Session
    try:
        if lib == "telethon":
            # Passing a file path directly creates an SQLite database there
            client = TelegramClient(session_base_path, req.api_id, req.api_hash)
            await client.start(bot_token=req.bot_token)
            await client.disconnect() # Crucial: Disconnect to save and unlock the DB file
            
        elif lib == "pyrogram":
            # workdir ensures the SQLite file goes into our cache folder
            client = PyrogramClient(
                name=token_hash, 
                workdir=CACHE_DIR,
                api_id=req.api_id, 
                api_hash=req.api_hash, 
                bot_token=req.bot_token
            )
            await client.start()
            await client.stop() # Crucial: Stop to save and unlock the DB file
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Telegram API Error: {str(e)}")

    # 3. Return the generated SQLite database file
    return FileResponse(
        path=file_path, 
        filename=f"{lib}_bot.session", 
        media_type="application/octet-stream"
    )
