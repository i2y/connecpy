from typing import Any, Callable

from conpy import context
from conpy.asgi import ConPyASGIApp
from conpy.interceptor import AsyncConpyServerInterceptor

import haberdasher_conpy
from service import HaberdasherService


class MyInterceptor(AsyncConpyServerInterceptor):
    def __init__(self, msg):
        self._msg = msg

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: context.ServiceContext,
        method_name: str,
    ) -> Any:
        print("intercepting " + method_name + " with " + self._msg)
        return await method(request, ctx)


my_interceptor_a = MyInterceptor("A")
my_interceptor_b = MyInterceptor("B")

service = haberdasher_conpy.HaberdasherServer(service=HaberdasherService())
app = ConPyASGIApp(
    interceptors=(my_interceptor_a, my_interceptor_b),
)
app.add_service(service)


# from starlette.middleware import Middleware

# from starlette.middleware.gzip import GZipMiddleware

# app = GZipMiddleware(app, minimum_size=1000)

from brotli_asgi import BrotliMiddleware

app = BrotliMiddleware(app, minimum_size=1)
