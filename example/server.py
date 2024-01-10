from typing import Any, Callable

from connecpy import context
from connecpy.asgi import ConnecpyASGIApp
from connecpy.interceptor import AsyncConnecpyServerInterceptor

import haberdasher_connecpy
from service import HaberdasherService


class MyInterceptor(AsyncConnecpyServerInterceptor):
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

service = haberdasher_connecpy.HaberdasherServer(service=HaberdasherService())
app = ConnecpyASGIApp(
    interceptors=(my_interceptor_a, my_interceptor_b),
)
app.add_service(service)


# from starlette.middleware import Middleware

# from starlette.middleware.gzip import GZipMiddleware

# app = GZipMiddleware(app, minimum_size=1000)

from brotli_asgi import BrotliMiddleware

app = BrotliMiddleware(app, minimum_size=1)
