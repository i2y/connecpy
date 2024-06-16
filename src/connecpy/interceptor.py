from abc import ABC, abstractmethod
from typing import Any, Callable, Protocol

from . import context


class AsyncServerInterceptor(Protocol):
    """Interceptor for asynchronous Connecpy server."""

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: context.ServiceContext,
        method_name: str,
    ) -> Any: ...


class AsyncConnecpyServerInterceptor(ABC):
    """
    Base class for asynchronous Connecpy server interceptors.
    """

    def make_interceptor(self, method: Callable, method_name: str):
        async def interceptor(request: Any, ctx: context.ServiceContext) -> Any:
            return await self.intercept(method, request, ctx, method_name)

        return interceptor

    @abstractmethod
    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: context.ServiceContext,
        method_name: str,
    ) -> Any:
        pass
