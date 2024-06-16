from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Hat(_message.Message):
    __slots__ = ("size", "color", "name")
    SIZE_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    size: int
    color: str
    name: str
    def __init__(self, size: _Optional[int] = ..., color: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class Size(_message.Message):
    __slots__ = ("inches",)
    INCHES_FIELD_NUMBER: _ClassVar[int]
    inches: int
    def __init__(self, inches: _Optional[int] = ...) -> None: ...
