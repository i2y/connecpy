import json
from typing import Generic, Iterator, TypeVar

from ._client_shared import handle_response_trailers
from ._codec import Codec
from ._compression import Compression
from ._protocol import ConnectWireError
from .code import Code
from .exceptions import ConnecpyException

_RES = TypeVar("_RES")


class EnvelopeReader(Generic[_RES]):
    _next_message_length: int | None

    def __init__(
        self, response_class: type[_RES], codec: Codec, compression: Compression
    ):
        self._buffer = bytearray()
        self._response_class = response_class
        self._codec = codec
        self._compression = compression

        self._next_message_length = None

    def feed(self, data: bytes) -> Iterator[_RES]:
        self._buffer.extend(data)
        return self.read_messages()

    def read_messages(self) -> Iterator[_RES]:
        while self._buffer:
            if self._next_message_length is not None:
                if len(self._buffer) < self._next_message_length + 5:
                    return

                compressed = self._buffer[0] & 0b01 != 0
                end_stream = self._buffer[0] & 0b10 != 0

                message_data = self._buffer[5 : 5 + self._next_message_length]
                self._buffer = self._buffer[5 + self._next_message_length :]
                self._next_message_length = None
                if compressed:
                    if self._compression.is_identity():
                        raise ConnecpyException(
                            Code.INTERNAL,
                            "protocol error: sent compressed message without compression support",
                        )
                    message_data = self._compression.decompress(message_data)

                if end_stream:
                    end_stream_message: dict = json.loads(message_data)
                    metadata = end_stream_message.get("metadata", None)
                    if metadata:
                        handle_response_trailers(metadata)
                    error = end_stream_message.get("error", None)
                    if error:
                        # Most likely a bug in the protocol, handling of unknown code is different for unary
                        # and streaming.
                        raise ConnectWireError.from_dict(
                            error, 500, Code.UNKNOWN
                        ).to_exception()
                    return

                res = self._response_class()
                self._codec.decode(message_data, res)
                yield res

            if len(self._buffer) < 5:
                return

            self._next_message_length = int.from_bytes(self._buffer[1:5], "big")
