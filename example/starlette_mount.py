from server import app as server_app
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

app = Starlette(
    routes=[
        Route(
            "/healthz",
            lambda _: PlainTextResponse("OK"),
        ),
        Mount(
            "/",
            app=server_app,
            name="haberdasher",
        ),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
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
