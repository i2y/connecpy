from typing import Any, Callable

from connecpy import context
from connecpy.cors import CORSMiddleware
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

app = haberdasher_connecpy.HaberdasherASGIApplication(
    HaberdasherService(),
    interceptors=(my_interceptor_a, my_interceptor_b),
)

# Add CORS support with default configuration
app = CORSMiddleware(app)
