from functools import partial
import json
from typing import Any, Callable, Dict, List, Tuple, Union

from google.protobuf import json_format, message

from . import errors
from . import exceptions


def json_decoder(body: bytes, data_obj: Any) -> Any:
    """Decode JSON data."""
    try:
        data = json.loads(body.decode("utf-8"))
        if issubclass(data_obj, message.Message):
            return json_format.ParseDict(data, data_obj())
        return data
    except Exception as e:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.InvalidArgument,
            message=f"Failed to decode JSON message: {str(e)}",
        )


def proto_decoder(body: bytes, data_obj: Any) -> Any:
    """Decode Protocol Buffer data."""
    try:
        msg = data_obj()
        msg.ParseFromString(body)
        return msg
    except Exception as e:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.InvalidArgument,
            message=f"Failed to decode protobuf message: {str(e)}",
        )


def json_encoder(value: Any, data_obj: Any) -> Tuple[bytes, Dict[str, List[str]]]:
    """Encode data as JSON."""
    try:
        if isinstance(value, message.Message):
            data = json_format.MessageToDict(value)
        else:
            data = value
        return (
            json.dumps(data).encode("utf-8"),
            {"Content-Type": ["application/json"]},
        )
    except Exception as e:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.Internal,
            message=f"Failed to encode JSON message: {str(e)}",
        )


def proto_encoder(
    value: message.Message, data_obj: Any
) -> Tuple[bytes, Dict[str, List[str]]]:
    """Encode data as Protocol Buffer."""
    try:
        return (
            value.SerializeToString(),
            {"Content-Type": ["application/proto"]},
        )
    except Exception as e:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.Internal,
            message=f"Failed to encode protobuf message: {str(e)}",
        )


def get_decoder_by_name(encoding_name: str) -> Union[Callable[[bytes, Any], Any], None]:
    """Get decoder function by encoding name."""
    decoders = {
        "json": json_decoder,
        "proto": proto_decoder,
    }
    return decoders.get(encoding_name)


def get_encoder(
    endpoint: Any, ctype: str
) -> Callable[[Any], Tuple[bytes, Dict[str, List[str]]]]:
    """Get encoder function by content type."""
    if ctype == "application/json":
        return partial(json_encoder, data_obj=endpoint.output)
    elif ctype == "application/proto":
        return partial(proto_encoder, data_obj=endpoint.output)
    else:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.BadRoute,
            message=f"unexpected Content-Type: {ctype}",
        )


def get_encoder_decoder_pair(
    endpoint: Any, ctype: str
) -> Tuple[
    Callable[[Any], Tuple[bytes, Dict[str, List[str]]]], Callable[[bytes, Any], Any]
]:
    """Get encoder and decoder functions for an endpoint and content type."""
    encoder = get_encoder(endpoint, ctype)
    decoder = get_decoder_by_name("proto" if ctype == "application/proto" else "json")
    if not decoder:
        raise exceptions.ConnecpyServerException(
            code=errors.Errors.Unimplemented,
            message=f"Unsupported encoding: {ctype}",
        )
    return encoder, partial(decoder, data_obj=endpoint.input)
