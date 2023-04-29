import uvicorn
from fastapi import FastAPI
import aiohttp

app = FastAPI()

JSON_URL = "https://tcec-chess.com/live.json"


@app.get("/")
async def route_root():
    async with aiohttp.ClientSession() as session:
        async with session.get(JSON_URL) as response:
            return await response.json()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=80)
