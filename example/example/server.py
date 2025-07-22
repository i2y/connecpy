from typing import Any, Callable

from connecpy.server import ServiceContext, ServerInterceptor

from . import haberdasher_connecpy
from .service import HaberdasherService


class MyInterceptor(ServerInterceptor):
    def __init__(self, msg):
        self._msg = msg

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: ServiceContext,
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
