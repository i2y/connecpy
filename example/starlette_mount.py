from typing import cast

from server import app as server_app
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

app = Starlette(
    routes=[
        Route(
            "/healthz",
            lambda _: PlainTextResponse("OK"),
        ),
        Mount(
            "/",
            app=cast(ASGIApp, server_app),
            name="haberdasher",
        ),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:9000"],
            allow_methods=["GET", "POST"],
            allow_headers=[
                "Content-Type",
                "Connect-Protocol-Version",
                "Connect-Timeout-Ms",
                "X-User-Agent",
            ],
        ),
    ],
)
