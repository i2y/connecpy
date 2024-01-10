import asyncio
from dataclasses import dataclass
from functools import partial, reduce
from typing import Callable, Generic, Tuple, TypeVar

from google.protobuf import json_format, message
from starlette import concurrency

from . import context
from . import exceptions
from . import errors
from . import interceptor
from . import server


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
    _async_proc: Callable[
        [
            T,
            context.ServiceContext,
        ],
        U,
    ] | None = None

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

    @staticmethod
    def json_decoder(body, data_obj):
        """
        Decodes a JSON request.

        Args:
            body (str): The JSON request body.
            data_obj: The data object to decode the request into.

        Returns:
            The decoded data object.

        Raises:
            exceptions.ConnecpyServerException: If the JSON request could not be decoded.
        """
        data = data_obj()
        try:
            json_format.Parse(body, data)
        except json_format.ParseError as exc:
            print(exc)
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Malformed,
                message="the json request could not be decoded",
            ) from exc
        return data

    @staticmethod
    def json_encoder(value, data_obj):
        """
        Encodes a service response to JSON.

        Args:
            value: The service response value.
            data_obj: The data object to encode the response from.

        Returns:
            The encoded JSON response and the content type.

        Raises:
            exceptions.ConnecpyServerException: If the service response type is invalid.
        """
        if not isinstance(value, data_obj):
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=f"bad service response type {type(value)}, expecting: {data_obj.DESCRIPTOR.full_name}",
            )

        return json_format.MessageToJson(
            value, preserving_proto_field_name=True
        ).encode("utf-8"), {"Content-Type": ["application/json"]}

    @staticmethod
    def proto_decoder(body, data_obj):
        """
        Decodes a protobuf request.

        Args:
            body (bytes): The protobuf request body.
            data_obj: The data object to decode the request into.

        Returns:
            The decoded data object.

        Raises:
            exceptions.ConnecpyServerException: If the protobuf request could not be decoded.
        """
        data = data_obj()
        try:
            data.ParseFromString(body)
        except message.DecodeError as exc:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Malformed,
                message="the protobuf request could not be decoded",
            ) from exc
        return data

    @staticmethod
    def proto_encoder(value, data_obj):
        """
        Encodes a service response to protobuf.

        Args:
            value: The service response value.
            data_obj: The data object to encode the response from.

        Returns:
            The encoded protobuf response and the content type.

        Raises:
            exceptions.ConnecpyServerException: If the service response type is invalid.
        """
        if not isinstance(value, data_obj):
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=f"bad service response type {type(value)}, expecting: {data_obj.DESCRIPTOR.full_name}",
            )

        return value.SerializeToString(), {"Content-Type": ["application/proto"]}

    def _get_encoder_decoder(self, endpoint, ctype: str):
        """
        Retrieves the appropriate encoder and decoder for a given endpoint and content type.

        Args:
            endpoint: The endpoint to retrieve the encoder and decoder for.
            ctype (str): The content type.

        Returns:
            The encoder and decoder functions.

        Raises:
            exceptions.ConnecpyServerException: If the content type is unexpected.
        """
        if "application/json" == ctype:
            decoder = partial(self.json_decoder, data_obj=endpoint.input)
            encoder = partial(self.json_encoder, data_obj=endpoint.output)
        elif "application/proto" == ctype:
            decoder = partial(self.proto_decoder, data_obj=endpoint.input)
            encoder = partial(self.proto_encoder, data_obj=endpoint.output)
        else:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message=f"unexpected Content-Type: {ctype}",
            )
        return encoder, decoder
