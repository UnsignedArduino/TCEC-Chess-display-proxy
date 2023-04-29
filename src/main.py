import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import aiohttp
import arrow
import chess.pgn
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

app = FastAPI()
service = ChromeService(executable_path=ChromeDriverManager().install())

SCRAPER_URL = "https://tcec-chess.com/"
JSON_URL = "https://tcec-chess.com/live.json"
PGN_URL = "https://tcec-chess.com/live.pgn"
TIMEZONE = "America/New_York"


@app.get("/metadata")
async def route_metadata():
    driver = webdriver.Chrome(service=service)
    driver.implicitly_wait(10)
    driver.get(SCRAPER_URL)

    async with aiohttp.ClientSession() as session:
        async with session.get(JSON_URL) as response:
            metadata = await response.json()

    headers = metadata["Headers"]

    start_time = arrow.get(headers["GameStartTime"].replace(" UTC", "Z")).to(
        TIMEZONE)
    time_control = int(headers["TimeControl"].split("+")[0])
    time_bonus = int(headers["TimeControl"].split("+")[1])

    get_ele = lambda id: driver.find_element(by=By.ID, value=id)

    wanted = {
        "event": {
            "name": headers["Event"],
            "round": headers["Round"]
        },
        "white": {
            "name": headers["White"].split(" ")[0],
            "version": headers["White"].split(" ")[1],
            "elo": headers["WhiteElo"],
            "eval": float(get_ele("eval0").text),
            "depth": get_ele("depth0").text,
            "speed": get_ele("speed0").text,
            "nodes": get_ele("node0").text,
            "remaining": get_ele("remain0").text
        },
        "black": {
            "name": headers["Black"].split(" ")[0],
            "version": headers["Black"].split(" ")[1],
            "elo": headers["BlackElo"],
            "eval": float(get_ele("eval1").text),
            "depth": get_ele("depth1").text,
            "speed": get_ele("speed1").text,
            "nodes": get_ele("node1").text,
            "remaining": get_ele("remain1").text
        },
        "game": {
            "start_absolute": start_time.format("HH:mm:ss MM/DD/YYYY"),
            "start_relative": start_time.humanize(granularity=["hour",
                                                               "minute"]),
            "opening": headers["Opening"],
            "time_control": "{0} + {1}".format(
                arrow.get(time_control).format("H:mm:ss"),
                arrow.get(time_bonus).format("m:ss"))
        },
    }

    driver.quit()

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
