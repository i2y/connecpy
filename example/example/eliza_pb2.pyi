from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class SayRequest(_message.Message):
    __slots__ = ("sentence",)
    SENTENCE_FIELD_NUMBER: _ClassVar[int]
    sentence: str
    def __init__(self, sentence: _Optional[str] = ...) -> None: ...

class SayResponse(_message.Message):
    __slots__ = ("sentence",)
    SENTENCE_FIELD_NUMBER: _ClassVar[int]
    sentence: str
    def __init__(self, sentence: _Optional[str] = ...) -> None: ...

class ConverseRequest(_message.Message):
    __slots__ = ("sentence",)
    SENTENCE_FIELD_NUMBER: _ClassVar[int]
    sentence: str
    def __init__(self, sentence: _Optional[str] = ...) -> None: ...

class ConverseResponse(_message.Message):
    __slots__ = ("sentence",)
    SENTENCE_FIELD_NUMBER: _ClassVar[int]
    sentence: str
    def __init__(self, sentence: _Optional[str] = ...) -> None: ...

class IntroduceRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class IntroduceResponse(_message.Message):
    __slots__ = ("sentence",)
    SENTENCE_FIELD_NUMBER: _ClassVar[int]
    sentence: str
    def __init__(self, sentence: _Optional[str] = ...) -> None: ...
