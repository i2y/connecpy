from typing import Awaitable, Callable, TypeVar

from connecpy.request import RequestContext

from . import haberdasher_connecpy
from .service import HaberdasherService

T = TypeVar("T")
U = TypeVar("U")


class MyInterceptor:
    def __init__(self, msg):
        self._msg = msg

    async def intercept_unary(
        self,
        next: Callable[[T, RequestContext], Awaitable[U]],
        request: T,
        ctx: RequestContext,
    ) -> U:
        print(f"intercepting {ctx.method().name} with {self._msg}")
        return await next(request, ctx)


my_interceptor_a = MyInterceptor("A")
my_interceptor_b = MyInterceptor("B")

app = haberdasher_connecpy.HaberdasherASGIApplication(
    HaberdasherService(),
    interceptors=(my_interceptor_a, my_interceptor_b),
)
