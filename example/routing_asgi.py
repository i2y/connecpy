from typing import cast

from haberdasher_connecpy import HaberdasherASGIApplication
from service import HaberdasherService
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

haberdasher_app = HaberdasherASGIApplication(HaberdasherService())


def strip_prefix(prefix: str, app: ASGIApp) -> ASGIApp:
    async def stripped_app(scope, receive, send):
        scope["path"] = scope["path"].removeprefix(prefix)
        return await app(scope, receive, send)

    return stripped_app


app = Starlette(
    routes=[
        Route(
            "/healthz",
            lambda _: PlainTextResponse("OK"),
        ),
        Mount(
            "/services",
            app=cast(ASGIApp, haberdasher_app),
        ),
        Mount(
            "/moreservices",
            app=Mount(
                haberdasher_app.path,
                app=strip_prefix("/moreservices", cast(ASGIApp, haberdasher_app)),
            ),
        ),
        Mount(
            haberdasher_app.path,
            app=cast(ASGIApp, haberdasher_app),
        ),
    ]
)
