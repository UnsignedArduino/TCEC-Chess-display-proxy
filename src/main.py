import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import aiohttp
import arrow
import chess.pgn
from io import StringIO

app = FastAPI()

JSON_URL = "https://tcec-chess.com/live.json"
PGN_URL = "https://tcec-chess.com/live.pgn"
TIMEZONE = "America/New_York"


@app.get("/metadata")
async def route_metadata():
    async with aiohttp.ClientSession() as session:
        async with session.get(JSON_URL) as response:
            metadata = await response.json()

    headers = metadata["Headers"]

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


@app.get("/moves", response_class=PlainTextResponse)
async def route_moves():
    async with aiohttp.ClientSession() as session:
        async with session.get(PGN_URL) as response:
            pgn = await response.text()

    game = chess.pgn.read_game(StringIO(pgn))
    exporter = chess.pgn.StringExporter(columns=None, headers=False,
                                        comments=False, variations=False)

    return game.accept(exporter)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=80)
