from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OpenEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[OpenEnum]
    FIRST: _ClassVar[OpenEnum]
    SECOND: _ClassVar[OpenEnum]

class ClosedEnum(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ZERO: _ClassVar[ClosedEnum]
    ONE: _ClassVar[ClosedEnum]
    TWO: _ClassVar[ClosedEnum]
UNKNOWN: OpenEnum
FIRST: OpenEnum
SECOND: OpenEnum
ZERO: ClosedEnum
ONE: ClosedEnum
TWO: ClosedEnum

class ExplicitFieldTest(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: int
    def __init__(self, name: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...

class ImplicitFieldTest(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: int
    def __init__(self, name: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...

class MixedFieldTest(_message.Message):
    __slots__ = ("explicit_field", "implicit_field")
    EXPLICIT_FIELD_FIELD_NUMBER: _ClassVar[int]
    IMPLICIT_FIELD_FIELD_NUMBER: _ClassVar[int]
    explicit_field: str
    implicit_field: str
    def __init__(self, explicit_field: _Optional[str] = ..., implicit_field: _Optional[str] = ...) -> None: ...

class EncodingTest(_message.Message):
    __slots__ = ("packed_ints", "expanded_ints")
    PACKED_INTS_FIELD_NUMBER: _ClassVar[int]
    EXPANDED_INTS_FIELD_NUMBER: _ClassVar[int]
    packed_ints: _containers.RepeatedScalarFieldContainer[int]
    expanded_ints: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, packed_ints: _Optional[_Iterable[int]] = ..., expanded_ints: _Optional[_Iterable[int]] = ...) -> None: ...

class FeatureTestRequest(_message.Message):
    __slots__ = ("explicit_test", "implicit_test", "mixed_test", "open_enum", "closed_enum", "encoding_test")
    EXPLICIT_TEST_FIELD_NUMBER: _ClassVar[int]
    IMPLICIT_TEST_FIELD_NUMBER: _ClassVar[int]
    MIXED_TEST_FIELD_NUMBER: _ClassVar[int]
    OPEN_ENUM_FIELD_NUMBER: _ClassVar[int]
    CLOSED_ENUM_FIELD_NUMBER: _ClassVar[int]
    ENCODING_TEST_FIELD_NUMBER: _ClassVar[int]
    explicit_test: ExplicitFieldTest
    implicit_test: ImplicitFieldTest
    mixed_test: MixedFieldTest
    open_enum: OpenEnum
    closed_enum: ClosedEnum
    encoding_test: EncodingTest
    def __init__(self, explicit_test: _Optional[_Union[ExplicitFieldTest, _Mapping]] = ..., implicit_test: _Optional[_Union[ImplicitFieldTest, _Mapping]] = ..., mixed_test: _Optional[_Union[MixedFieldTest, _Mapping]] = ..., open_enum: _Optional[_Union[OpenEnum, str]] = ..., closed_enum: _Optional[_Union[ClosedEnum, str]] = ..., encoding_test: _Optional[_Union[EncodingTest, _Mapping]] = ...) -> None: ...

class FeatureTestResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: str
    def __init__(self, result: _Optional[str] = ...) -> None: ...
