"""Asynchronous client creation for Connect and gRPC protocols."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Protocol

from .base import CallOptions
from .connect_async import ConnectTransportAsync
from .grpc_async import GrpcTransportAsync

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from connecpy.method import MethodInfo


class TransportAsync(Protocol):
    """Protocol for async transport implementations."""

    async def unary_unary(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> Any: ...

    async def unary_stream(
        self, method: MethodInfo, request: Any, call_options: CallOptions | None = None
    ) -> AsyncIterator[Any]: ...

    async def stream_unary(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> Any: ...

    async def stream_stream(
        self,
        method: MethodInfo,
        stream: AsyncIterator[Any],
        call_options: CallOptions | None = None,
    ) -> AsyncIterator[Any]: ...

    async def close(self) -> None: ...


def create_client(
    service_class: type[Any],
    transport: TransportAsync | ConnectTransportAsync | GrpcTransportAsync,
) -> Any:
    """Create an asynchronous client for the given service using the specified transport.

    Args:
        service_class: The service class containing metadata (e.g., Haberdasher)
        transport: The async transport to use (Connect or gRPC)

    Returns:
        An async client instance appropriate for the transport type

    Example:
        ```python
        # For Connect protocol
        from connecpy.transport import ConnectTransportAsync, create_client
        from example.haberdasher_connecpy import Haberdasher

        connect_transport = ConnectTransportAsync("http://localhost:3000")
        client = create_client(Haberdasher, connect_transport)
        # Returns HaberdasherClient instance

        # For gRPC protocol with async stub
        from connecpy.transport import GrpcTransportAsync, create_client

        grpc_transport = GrpcTransportAsync("localhost:50051")
        client = create_client(Haberdasher, grpc_transport)
        # Returns GrpcClientWrapperAsync wrapping async gRPC stub
        ```
    """
    if isinstance(transport, ConnectTransportAsync):
        # For Connect transport, return the existing ConnecpyClient-based client
        # Handle both Haberdasher and HaberdasherSync class names
        base_name = service_class.__name__
        base_name = base_name.removesuffix("Sync")  # Remove "Sync" suffix

        client_class_name = (
            f"{base_name}Client"  # Async client doesn't have Sync suffix
        )
        module = service_class.__module__

        # Import the client class dynamically
        mod = importlib.import_module(module)
        client_class = getattr(mod, client_class_name)

        # Create the client with the transport's parameters
        return client_class(
            address=transport.address,
            proto_json=transport.proto_json,
            accept_compression=transport.accept_compression,
            send_compression=transport.send_compression,
            timeout_ms=transport.timeout_ms,
            read_max_bytes=transport.read_max_bytes,
            interceptors=transport.interceptors,
            session=transport.session,
        )

    if isinstance(transport, GrpcTransportAsync):
        # For gRPC transport, use the generated static wrapper
        # Handle both Haberdasher and HaberdasherSync class names
        base_name = service_class.__name__
        base_name = base_name.removesuffix("Sync")  # Remove "Sync" suffix

        wrapper_class_name = (
            f"{base_name}GrpcWrapper"  # Async wrapper doesn't have Sync suffix
        )
        stub_class_name = f"{base_name}Stub"
        module = service_class.__module__

        # Import the wrapper class from the same module as the service
        mod = importlib.import_module(module)
        wrapper_class = getattr(mod, wrapper_class_name)

        # Try to import the gRPC stub from the _pb2_grpc module
        module_parts = module.split(".")
        if module_parts[-1].endswith("_connecpy"):
            # Replace _connecpy with _pb2_grpc
            base_name_without_suffix = module_parts[-1][:-9]  # Remove "_connecpy"
            module_parts[-1] = f"{base_name_without_suffix}_pb2_grpc"
            grpc_module_name = ".".join(module_parts)
        else:
            # Fallback: try adding _pb2_grpc
            base_module = module.rsplit(".", 1)[0]
            grpc_module_name = f"{base_module}_pb2_grpc"

        try:
            grpc_mod = importlib.import_module(grpc_module_name)
            stub_class = getattr(grpc_mod, stub_class_name)

            # Create the stub with the transport's channel
            stub = stub_class(transport._channel)  # noqa: SLF001

            # Create and return the wrapper
            return wrapper_class(stub)  # type: ignore[return-value]
        except (ImportError, AttributeError) as e:
            msg = (
                f"Could not import gRPC stub {stub_class_name} from {grpc_module_name}. "
                f"Make sure the proto file was compiled with grpc_tools: {e}"
            )
            raise ImportError(msg) from e

    else:
        # Generic transport with TransportAsync protocol
        class DynamicAsyncClient:
            def __init__(self, transport: TransportAsync, service_info: Any) -> None:
                self._transport = transport
                self._service_info = service_info

                # Create methods dynamically
                methods = (
                    service_info.get("methods", {})
                    if isinstance(service_info, dict)
                    else getattr(service_info, "methods", {})
                )
                for method_name, method_info in methods.items():
                    method = self._create_method(method_info)
                    setattr(self, method_name, method)

            def _create_method(self, method_info: MethodInfo) -> Any:
                async def method_impl(
                    request: Any,
                    *,
                    headers: dict[str, str] | None = None,
                    timeout_ms: int | None = None,
                ) -> Any:
                    call_options = CallOptions(
                        headers=headers or {}, timeout_ms=timeout_ms
                    )

                    # Determine the RPC type and call appropriate transport method
                    # This would need to be determined from method_info
                    # For now, assume unary-unary
                    return await self._transport.unary_unary(
                        method_info, request, call_options
                    )

                return method_impl

        service_info = getattr(service_class, "_service_info", None)
        return DynamicAsyncClient(transport, service_info)  # type: ignore[arg-type]
