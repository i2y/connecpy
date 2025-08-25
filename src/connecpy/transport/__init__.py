"""Transport API for protocol-agnostic RPC clients.

WARNING: The Transport API is experimental and may change in future versions.
Use with caution in production environments.
"""

import warnings

from .base import CallOptions, RetryPolicy
from .client import create_client_sync
from .client_async import create_client
from .connect import ConnectTransport
from .connect_async import ConnectTransportAsync
from .grpc import GrpcTransport
from .grpc_async import GrpcTransportAsync

# Emit a warning when the transport module is imported
warnings.warn(
    "The Transport API is experimental and may change in future versions. "
    "Use with caution in production environments.",
    FutureWarning,
    stacklevel=2,
)

__all__ = [
    "CallOptions",
    "ConnectTransport",
    "ConnectTransportAsync",
    "GrpcTransport",
    "GrpcTransportAsync",
    "RetryPolicy",
    "create_client",
    "create_client_sync",
]
