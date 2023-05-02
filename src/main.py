import math

import uvicorn
from fastapi import FastAPI
from fastapi.responses import Response, PlainTextResponse
import aiohttp
import arrow
import chess.pgn
import chess.svg
from io import StringIO, BytesIO
from si_prefix import si_format
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
import fitz
from PIL import Image

JSON_URL = "https://tcec-chess.com/live.json"
PGN_URL = "https://tcec-chess.com/live.pgn"
TIMEZONE = "America/New_York"

app = FastAPI()


@app.get("/metadata.json")
async def route_metadata_json():
    async with aiohttp.ClientSession() as session:
        async with session.get(JSON_URL) as response:
            metadata = await response.json()

    headers = metadata["Headers"]
    moves = metadata["Moves"]

    start_time = arrow.get(headers["GameStartTime"].replace(" UTC", "Z")).to(
        TIMEZONE)
    time_control = int(headers["TimeControl"].split("+")[0])
    time_bonus = int(headers["TimeControl"].split("+")[1])

    move_count = len(moves)
    is_whites_move = move_count % 2 == 1
    last_white_move = None
    last_black_move = None

    if move_count >= 2:
        if is_whites_move:
            last_white_move = moves[-1]
            last_black_move = moves[-2]
        else:
            last_black_move = moves[-1]
            last_white_move = moves[-2]
    elif move_count == 1:
        last_white_move = moves[-1]

    wanted = {
        "event": {
            "name": headers["Event"],
            "round": headers["Round"]
        },
        "white": {
            "name": headers["White"].split(" ")[0],
            "version": headers["White"].split(" ")[1],
            "elo": headers["WhiteElo"],
            "book": last_white_move[
                "book"] if last_white_move is not None else None
        },
        "black": {
            "name": headers["Black"].split(" ")[0],
            "version": headers["Black"].split(" ")[1],
            "elo": headers["BlackElo"],
            "book": last_black_move[
                "book"] if last_black_move is not None else None
        },
        "game": {
            "start_absolute": start_time.format("HH:mm:ss MM/DD/YYYY"),
            "start_relative": start_time.humanize(granularity=["hour",
                                                               "minute"]),
            "opening": headers["Opening"],
            "time_control": "{0} + {1}".format(
                arrow.get(time_control).format("H:mm:ss"),
                arrow.get(time_bonus).format("m:ss")),
            "moves": str(move_count)
        },
    }

    if last_white_move is not None and not last_white_move["book"]:
        wanted["white"] |= {
            "eval": last_white_move["wv"],
            "depth": last_white_move["d"] + "/" + last_white_move["sd"],
            "speed": si_format(int(last_white_move["s"])) + "n/s",
            "nodes": si_format(int(last_white_move["n"])),
            "move_time": arrow.get(
                int(last_white_move["mt"]) / 1000
            ).format("m:ss"),
            "remaining_time": arrow.get(
                int(last_white_move["tl"]) / 1000
            ).format("H:mm:ss")
        }

    if last_black_move is not None and not last_black_move["book"]:
        wanted["black"] |= {
            "eval": last_black_move["wv"],
            "depth": last_black_move["d"] + "/" + last_black_move["sd"],
            "speed": si_format(int(last_black_move["s"])) + "n/s",
            "nodes": si_format(int(last_black_move["n"])),
            "move_time": arrow.get(
                int(last_black_move["mt"]) / 1000
            ).format("m:ss"),
            "remaining_time": arrow.get(
                int(last_black_move["tl"]) / 1000
            ).format("H:mm:ss")
        }

    return wanted


@app.get("/moves.pgn", response_class=PlainTextResponse)
async def route_moves_pgn():
    async with aiohttp.ClientSession() as session:
        async with session.get(PGN_URL) as response:
            pgn = await response.text()

    game = chess.pgn.read_game(StringIO(pgn))
    exporter = chess.pgn.StringExporter(columns=None, headers=False,
                                        comments=False, variations=False)

    return game.accept(exporter)


async def get_board_image(size: int) -> Image:
    async with aiohttp.ClientSession() as session:
        async with session.get(PGN_URL) as response:
            pgn = await response.text()
        async with session.get(JSON_URL) as response:
            metadata = await response.json()

    game = chess.pgn.read_game(StringIO(pgn))
    board = game.board()
    last_move = None
    for move in game.mainline_moves():
        board.push(move)
        last_move = move

    ponder = metadata["Moves"]
    arrows = []
    if len(ponder) > 0 and "pv" in ponder[-1] and \
            len(ponder[-1]["pv"]["Moves"]) > 1:
        next_move = ponder[-1]["pv"]["Moves"][1]
        move = chess.Move(chess.parse_square(next_move["from"]),
                          chess.parse_square(next_move["to"]))
        if move != last_move:
            arrows.append(
                chess.svg.Arrow(
                    move.from_square,
                    move.to_square,
                    color="#DDDDDDCC"
                )
            )

    svg_buf = BytesIO()
    svg_buf.write(chess.svg.board(board,
                                  lastmove=last_move,
                                  arrows=arrows,
                                  colors={
                                      "square light lastmove": "#A5A5A5",
                                      "square dark lastmove": "#656565",
                                  }).encode("utf-8"))
    svg_buf.seek(0)
    drawing = svg2rlg(svg_buf)
    pdf = renderPDF.drawToString(drawing)
    doc = fitz.Document(stream=pdf)
    pix = doc.load_page(0).get_pixmap(alpha=True, dpi=300)
    png_bytes = BytesIO()
    png_bytes.write(pix.tobytes(output="png"))
    png_bytes.seek(0)

    return Image.open(png_bytes).resize((size, size)).convert("L")


@app.get("/image.png")
async def route_image_png(size: int = 300):
    new_image = await get_board_image(size)
    resized_buf = BytesIO()
    new_image.save(resized_buf, "png")
    resized_buf.seek(0)

    return Response(content=resized_buf.read(), status_code=200,
                    media_type="image/png")


@app.get("/image.jpg")
async def route_image_jpg(size: int = 300):
    new_image = (await get_board_image(size)).convert("RGB")
    resized_buf = BytesIO()
    new_image.save(resized_buf, "jpeg")
    resized_buf.seek(0)

    return Response(content=resized_buf.read(), status_code=200,
                    media_type="image/jpg")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=80)
