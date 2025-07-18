import asyncio
from dataclasses import dataclass
from functools import reduce
from typing import Callable, Generic, Iterable, TypeVar, Union

from . import context
from . import interceptor


T = TypeVar("T")
U = TypeVar("U")


@dataclass
class Endpoint(Generic[T, U]):
    """
    Represents an endpoint in a service.

    Attributes:
        service_name (str): The name of the service.
        name (str): The name of the endpoint.
        function (Callable[[T, context.ServiceContext], U]): The function that implements the endpoint.
        input (type): The type of the input parameter.
        output (type): The type of the output parameter.
        allowed_methods (list[str]): The allowed HTTP methods for the endpoint.
        _async_proc (Callable[[T, context.ServiceContext], U] | None): The asynchronous function that implements the endpoint.
    """

    service_name: str
    name: str
    function: Callable[
        [
            T,
            context.ServiceContext,
        ],
        U,
    ]
    input: type
    output: type
    allowed_methods: tuple[str, ...] = ("POST",)
    _async_proc: Union[
        Callable[
            [
                T,
                context.ServiceContext,
            ],
            U,
        ],
        None,
    ] = None
    _proc: Union[
        Callable[
            [
                T,
                context.ServiceContext,
            ],
            U,
        ],
        None,
    ] = None

    def make_async_proc(
        self,
        interceptors: Iterable[interceptor.AsyncConnecpyServerInterceptor],
    ) -> Callable[[T, context.ServiceContext], U]:
        """
        Creates an asynchronous function that implements the endpoint.

        Args:
            interceptors (Iterable[interceptor.AsyncConnecpyServerInterceptor]): The interceptors to apply to the endpoint.

        Returns:
            Callable[[T, context.ServiceContext], U]: The asynchronous function that implements the endpoint.
        """
        if self._async_proc is not None:
            return self._async_proc

        method_name = self.name
        reversed_interceptors = reversed(tuple(interceptors))
        self._async_proc = reduce(  # type: ignore
            lambda acc, interceptor: interceptor.make_interceptor(acc, method_name),
            reversed_interceptors,
            asynchronize(self.function),
        )  # type: ignore

        return self._async_proc  # type: ignore

    def make_proc(
        self,
    ) -> Callable[[T, context.ServiceContext], U]:
        """
        Creates an asynchronous function that implements the endpoint.

        Args:
            interceptors (Tuple[interceptor.AsyncConnecpyServerInterceptor, ...]): The interceptors to apply to the endpoint.

        Returns:
            Callable[[T, context.ServiceContext], U]: The asynchronous function that implements the endpoint.
        """
        if self._proc is not None:
            return self._proc

        self._proc = self.function

        return self._proc  # type: ignore


def thread_pool_runner(func):
    async def run(request, ctx: context.ServiceContext):
        return await asyncio.to_thread(func, request, ctx)

    return run


def asynchronize(func) -> Callable:
    """
    Decorator that converts a synchronous function into an asynchronous function.

    If the input function is already a coroutine function, it is returned as is.
    Otherwise, it is wrapped in a thread pool runner to execute it asynchronously.

    Args:
        func: The synchronous function to be converted.

    Returns:
        The converted asynchronous function.

    """
    if asyncio.iscoroutinefunction(func):
        return func
    else:
        return thread_pool_runner(func)
