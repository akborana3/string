from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import time
import hashlib

app = FastAPI(title="Telegram Session API")

# Setup caching directory and expiry time (30 minutes)
CACHE_DIR = "session_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_EXPIRY = 30 * 60 

class SessionRequest(BaseModel):
    api_id: int
    api_hash: str
    bot_token: str
    library: str = "telethon"

@app.post("/generate")
async def generate_session(req: SessionRequest):
    if req.library.lower() != "telethon":
        raise HTTPException(status_code=400, detail="Only 'telethon' is supported right now.")

    # Create a unique filename hash based on the bot token
    token_hash = hashlib.md5(req.bot_token.encode()).hexdigest()
    file_path = os.path.join(CACHE_DIR, f"{token_hash}.session")

    # 1. Check Cache: Does the file exist and is it under 30 minutes old?
    if os.path.exists(file_path):
        file_age = time.time() - os.path.getmtime(file_path)
        if file_age < CACHE_EXPIRY:
            return FileResponse(
                path=file_path, 
                filename="string.session", 
                media_type="text/plain"
            )
        else:
            # Delete expired session file
            os.remove(file_path)

    # 2. Generate New Session
    client = TelegramClient(StringSession(), req.api_id, req.api_hash)
    
    try:
        # Start the client using the bot token
        await client.start(bot_token=req.bot_token)
        session_string = client.session.save()
        await client.disconnect()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Telegram API Error: {str(e)}")

    # 3. Save to Cache
    with open(file_path, "w") as f:
        f.write(session_string)

    # 4. Return as a downloadable file
    return FileResponse(
        path=file_path, 
        filename="string.session", 
        media_type="text/plain"
    )
