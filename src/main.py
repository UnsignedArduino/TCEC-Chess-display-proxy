import uvicorn
from fastapi import FastAPI
import aiohttp
import arrow

app = FastAPI()

JSON_URL = "https://tcec-chess.com/live.json"
TIMEZONE = "America/New_York"


@app.get("/metadata")
async def route_metadata():
    async with aiohttp.ClientSession() as session:
        async with session.get(JSON_URL) as response:
            live = await response.json()

    headers = live["Headers"]

    start_time = arrow.get(headers["GameStartTime"].replace(" UTC", "Z")).to(
        TIMEZONE)
    time_control = int(headers["TimeControl"].split("+")[0])
    time_bonus = int(headers["TimeControl"].split("+")[1])

    wanted = {
        "event": {
            "name": headers["Event"],
            "round": headers["Round"]
        },
        "white": {
            "name": headers["White"],
            "elo": headers["WhiteElo"]
        },
        "black": {
            "name": headers["Black"],
            "elo": headers["BlackElo"]
        },
        "game": {
            "start_absolute": start_time.format("HH:mm:ss MM/DD/YYYY"),
            "start_relative": start_time.humanize(granularity=["hour",
                                                               "minute"]),
            "opening": headers["Opening"],
            "time_control": "{0} + {1}".format(
                arrow.get(time_control).format("H:mm:ss"),
                arrow.get(time_bonus).format("m:ss"))
        }
    }

    return wanted


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=80)
