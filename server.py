#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# web-boardimage is an HTTP service that renders chess board images.
# Copyright (C) 2016-2017 Niklas Fiekas <niklas.fiekas@backscattering.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""An HTTP service that renders chess board images"""

import argparse
import asyncio
import aiohttp.web
import aiohttp_cors
import chess
import chess.svg
import cairosvg
import re


class Service:
    def __init__(self, css=None):
        self.css = css

    def make_svg(self, request):
        try:
            parts = request.query["fen"].replace("_", " ").split(" ", 1)
            board = chess.BaseBoard("/".join(parts[0].split("/")[0:8]))
        except KeyError:
            raise aiohttp.web.HTTPBadRequest(reason="fen required")
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="invalid fen")

        try:
            size = min(max(int(request.query.get("size", 360)), 16), 1024)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="size is not a number")

        try:
            uci = request.query.get("lastMove") or request.query["lastmove"]
            lastmove = chess.Move.from_uci(uci)
        except KeyError:
            lastmove = None
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="lastMove is not a valid uci move")

        try:
            check = chess.SQUARE_NAMES.index(request.query["check"])
        except KeyError:
            check = None
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="check is not a valid square name")

        try:
            arrows = [arrow(s.strip()) for s in request.query.get("arrows", "").split(",") if s.strip()]
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(reason="invalid arrow")

        flipped = request.query.get("orientation", "white") == "black"

        return chess.svg.board(board, coordinates=False, flipped=flipped, lastmove=lastmove, check=check, arrows=arrows, size=size, style=self.css)

    @asyncio.coroutine
    def render_svg(self, request):
        return aiohttp.web.Response(text=self.make_svg(request), content_type="image/svg+xml")

    @asyncio.coroutine
    def render_png(self, request):
        svg_data = self.make_svg(request)
        png_data = cairosvg.svg2png(bytestring=svg_data)
        return aiohttp.web.Response(body=png_data, content_type="image/png")


def arrow(s):
    tail = chess.SQUARE_NAMES.index(s[:2])
    head = chess.SQUARE_NAMES.index(s[2:]) if len(s) > 2 else tail
    return chess.svg.Arrow(tail, head)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", "-p", type=int, default=8080, help="web server port")
    parser.add_argument("--bind", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--css", type=argparse.FileType("r"))
    args = parser.parse_args()

    app = aiohttp.web.Application()

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
    })

    service = Service(args.css.read() if args.css else None)
    app.router.add_get("/board.png", service.render_png)
    app.router.add_get("/board.svg", service.render_svg)

    for route in list(app.router.routes()):
        cors.add(route)

    aiohttp.web.run_app(app, port=args.port, host=args.bind, access_log=None)
