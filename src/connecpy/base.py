import asyncio
from dataclasses import dataclass
from functools import reduce
from typing import Callable, Generic, Tuple, TypeVar, Union

from starlette import concurrency

from . import context
from . import exceptions
from . import errors
from . import interceptor
from . import server
from . import encoding


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
    allowed_methods: tuple[str] = ("POST",)
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
        interceptors: Tuple[interceptor.AsyncConnecpyServerInterceptor, ...],
    ) -> Callable[[T, context.ServiceContext], U]:
        """
        Creates an asynchronous function that implements the endpoint.

        Args:
            interceptors (Tuple[interceptor.AsyncConnecpyServerInterceptor, ...]): The interceptors to apply to the endpoint.

        Returns:
            Callable[[T, context.ServiceContext], U]: The asynchronous function that implements the endpoint.
        """
        if self._async_proc is not None:
            return self._async_proc

        method_name = self.name
        reversed_interceptors = reversed(interceptors)
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
    async def run(request, ctx: context.ConnecpyServiceContext):
        return await concurrency.run_in_threadpool(func, request, ctx)

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


class ConnecpyBaseApp(object):
    """
    Represents the base application class for Connecpy servers.

    Args:
        interceptors (Tuple[interceptor.AsyncConnecpyServerInterceptor, ...]): A tuple of interceptors to be applied to the server.
        prefix (str): The prefix to be added to the service endpoints.
        max_receive_message_length (int): The maximum length of the received messages.

    Attributes:
        _interceptors (Tuple[interceptor.AsyncConnecpyServerInterceptor, ...]): The interceptors applied to the server.
        _prefix (str): The prefix added to the service endpoints.
        _services (dict): A dictionary of services registered with the server.
        _max_receive_message_length (int): The maximum length of the received messages.

    Methods:
        add_service: Adds a service to the server.
        _get_endpoint: Retrieves the endpoint for a given path.
        json_decoder: Decodes a JSON request.
        json_encoder: Encodes a service response to JSON.
        proto_decoder: Decodes a protobuf request.
        proto_encoder: Encodes a service response to protobuf.
        _get_encoder_decoder: Retrieves the appropriate encoder and decoder for a given endpoint and content type.
    """

    def __init__(
        self,
        interceptors: Tuple[interceptor.AsyncConnecpyServerInterceptor, ...] = (),
        prefix="",
        max_receive_message_length=1024 * 100 * 100,
    ):
        self._interceptors = interceptors
        self._prefix = prefix
        self._services = {}
        self._max_receive_message_length = max_receive_message_length

    def add_service(self, svc: server.ConnecpyServer):
        """
        Adds a service to the server.

        Args:
            svc (server.ConnecpyServer): The service to be added.
        """
        self._services[self._prefix + svc.prefix] = svc

    def _get_endpoint(self, path):
        """
        Retrieves the endpoint for a given path.

        Args:
            path (str): The path of the endpoint.

        Returns:
            The endpoint for the given path.

        Raises:
            exceptions.ConnecpyServerException: If the endpoint is not found.
        """
        svc = self._services.get(path.rsplit("/", 1)[0], None)
        if svc is None:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.NotFound, message="not found"
            )

        return svc.get_endpoint(path[len(self._prefix) :])

    def _get_encoder_decoder(self, endpoint, ctype: str):
        """
        Retrieves the appropriate encoder and decoder for a given endpoint and content type.

        Args:
            endpoint: The endpoint to retrieve the encoder and decoder for.
            ctype (str): The content type.

        Returns:
            The encoder and decoder functions.
        """
        return encoding.get_encoder_decoder_pair(endpoint, ctype)
