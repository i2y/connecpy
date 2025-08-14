from typing import Any, Protocol, TypeVar

from google.protobuf.json_format import MessageToJson
from google.protobuf.json_format import Parse as MessageFromJson
from google.protobuf.message import Message

CODEC_NAME_PROTO = "proto"
CODEC_NAME_JSON = "json"
# Follow connect-go's hacky approach to handling charset parameter
# https://github.com/connectrpc/connect-go/blob/fe4915717d32438c40a24a50e3895271d4c24751/codec.go#L31
CODEC_NAME_JSON_CHARSET_UTF8 = "json; charset=utf-8"


T = TypeVar("T")


class Codec(Protocol):
    def name(self) -> str:
        """Returns the name of the codec."""
        ...

    def encode(self, message: Any) -> bytes:
        """Marshals the given message."""
        ...

    def decode(self, data: bytes | bytearray, message: T) -> T:
        """Unmarshals the given message."""
        ...


class ProtoBinaryCodec(Codec):
    """Codec for Protocol bytes | bytearrays binary format."""

    def name(self) -> str:
        return "proto"

    def encode(self, message: Any) -> bytes:
        if not isinstance(message, Message):
            msg = "Expected a protobuf Message instance"
            raise TypeError(msg)
        return message.SerializeToString()

    def decode(self, data: bytes | bytearray, message: T) -> T:
        if not isinstance(message, Message):
            msg = "Expected a protobuf Message instance"
            raise TypeError(msg)
        message.ParseFromString(data)  # pyright: ignore[reportArgumentType] - type is incorrect
        return message


class ProtoJSONCodec(Codec):
    """Codec for Protocol bytes | bytearrays JSON format."""

    def name(self) -> str:
        return "json"

    def encode(self, message: Any) -> bytes:
        if not isinstance(message, Message):
            msg = "Expected a protobuf Message instance"
            raise TypeError(msg)
        return MessageToJson(message).encode()

    def decode(self, data: bytes | bytearray, message: T) -> T:
        if not isinstance(message, Message):
            msg = "Expected a protobuf Message instance"
            raise TypeError(msg)
        MessageFromJson(data, message)  # pyright: ignore[reportArgumentType] - type is incorrect
        return message


# TODO: Codecs can generally be customized per handler instead of as a global
# registry, though the usage isn't common.
_proto_binary_codec = ProtoBinaryCodec()
_proto_json_codec = ProtoJSONCodec()
_codecs = {
    CODEC_NAME_PROTO: _proto_binary_codec,
    CODEC_NAME_JSON: _proto_json_codec,
    CODEC_NAME_JSON_CHARSET_UTF8: _proto_json_codec,
}


def get_proto_binary_codec() -> Codec:
    """Returns the Protocol bytes | bytearrays binary codec."""
    return _proto_binary_codec


def get_proto_json_codec() -> Codec:
    """Returns the Protocol bytes | bytearrays JSON codec."""
    return _proto_json_codec


def get_codec(name: str) -> Codec | None:
    """Returns the codec with the given name."""
    return _codecs.get(name)
