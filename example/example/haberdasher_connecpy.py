# -*- coding: utf-8 -*-
# Generated by https://github.com/i2y/connecpy/protoc-gen-connecpy.  DO NOT EDIT!
# source: example/haberdasher.proto

from typing import Iterable, Optional, Protocol, Union

import httpx

from connecpy.client import ConnecpyClient, ConnecpyClientSync, RequestHeaders
from connecpy.code import Code
from connecpy.exceptions import ConnecpyServerException
from connecpy.server import (
    ConnecpyASGIApplication,
    ConnecpyWSGIApplication,
    Endpoint,
    ServerInterceptor,
    ServiceContext,
)
import example.haberdasher_pb2 as example_dot_haberdasher__pb2
import google.protobuf.empty_pb2 as google_dot_protobuf_dot_empty__pb2


class Haberdasher(Protocol):
    async def MakeHat(
        self, req: example_dot_haberdasher__pb2.Size, ctx: ServiceContext
    ) -> example_dot_haberdasher__pb2.Hat:
        raise ConnecpyServerException(
            code=Code.UNIMPLEMENTED, message="Not implemented"
        )

    async def DoNothing(
        self, req: google_dot_protobuf_dot_empty__pb2.Empty, ctx: ServiceContext
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        raise ConnecpyServerException(
            code=Code.UNIMPLEMENTED, message="Not implemented"
        )


class HaberdasherASGIApplication(ConnecpyASGIApplication):
    def __init__(
        self,
        service: Haberdasher,
        *,
        interceptors: Iterable[ServerInterceptor] = (),
        max_receive_message_length=1024 * 100 * 100,
    ):
        super().__init__(
            path="/i2y.connecpy.example.Haberdasher",
            endpoints={
                "/i2y.connecpy.example.Haberdasher/MakeHat": Endpoint[
                    example_dot_haberdasher__pb2.Size, example_dot_haberdasher__pb2.Hat
                ](
                    service_name="Haberdasher",
                    name="MakeHat",
                    function=getattr(service, "MakeHat"),
                    input=example_dot_haberdasher__pb2.Size,
                    output=example_dot_haberdasher__pb2.Hat,
                    allowed_methods=("GET", "POST"),
                ),
                "/i2y.connecpy.example.Haberdasher/DoNothing": Endpoint[
                    google_dot_protobuf_dot_empty__pb2.Empty,
                    google_dot_protobuf_dot_empty__pb2.Empty,
                ](
                    service_name="Haberdasher",
                    name="DoNothing",
                    function=getattr(service, "DoNothing"),
                    input=google_dot_protobuf_dot_empty__pb2.Empty,
                    output=google_dot_protobuf_dot_empty__pb2.Empty,
                    allowed_methods=("POST",),
                ),
            },
            interceptors=interceptors,
            max_receive_message_length=max_receive_message_length,
        )

    @property
    def service_name(self):
        return "i2y.connecpy.example.Haberdasher"


class HaberdasherClient(ConnecpyClient):
    async def MakeHat(
        self,
        request: example_dot_haberdasher__pb2.Size,
        *,
        headers: Optional[RequestHeaders] = None,
        timeout_ms: Optional[int] = None,
        server_path_prefix: str = "",
        session: Union[httpx.AsyncClient, None] = None,
        use_get: bool = False,
    ) -> example_dot_haberdasher__pb2.Hat:
        method = "GET" if use_get else "POST"
        return await self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/MakeHat",
            method=method,
            headers=headers,
            request=request,
            timeout_ms=timeout_ms,
            response_class=example_dot_haberdasher__pb2.Hat,
            session=session,
        )

    async def DoNothing(
        self,
        request: google_dot_protobuf_dot_empty__pb2.Empty,
        *,
        headers: Optional[RequestHeaders] = None,
        timeout_ms: Optional[int] = None,
        server_path_prefix: str = "",
        session: Union[httpx.AsyncClient, None] = None,
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        method = "POST"
        return await self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/DoNothing",
            method=method,
            headers=headers,
            request=request,
            timeout_ms=timeout_ms,
            response_class=google_dot_protobuf_dot_empty__pb2.Empty,
            session=session,
        )


class HaberdasherSync(Protocol):
    def MakeHat(
        self, req: example_dot_haberdasher__pb2.Size, ctx: ServiceContext
    ) -> example_dot_haberdasher__pb2.Hat:
        raise ConnecpyServerException(
            code=Code.UNIMPLEMENTED, message="Not implemented"
        )

    def DoNothing(
        self, req: google_dot_protobuf_dot_empty__pb2.Empty, ctx: ServiceContext
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        raise ConnecpyServerException(
            code=Code.UNIMPLEMENTED, message="Not implemented"
        )


class HaberdasherWSGIApplication(ConnecpyWSGIApplication):
    def __init__(self, service: HaberdasherSync):
        super().__init__(
            path="/i2y.connecpy.example.Haberdasher",
            endpoints={
                "/i2y.connecpy.example.Haberdasher/MakeHat": Endpoint[
                    example_dot_haberdasher__pb2.Size, example_dot_haberdasher__pb2.Hat
                ](
                    service_name="Haberdasher",
                    name="MakeHat",
                    function=getattr(service, "MakeHat"),
                    input=example_dot_haberdasher__pb2.Size,
                    output=example_dot_haberdasher__pb2.Hat,
                    allowed_methods=("GET", "POST"),
                ),
                "/i2y.connecpy.example.Haberdasher/DoNothing": Endpoint[
                    google_dot_protobuf_dot_empty__pb2.Empty,
                    google_dot_protobuf_dot_empty__pb2.Empty,
                ](
                    service_name="Haberdasher",
                    name="DoNothing",
                    function=getattr(service, "DoNothing"),
                    input=google_dot_protobuf_dot_empty__pb2.Empty,
                    output=google_dot_protobuf_dot_empty__pb2.Empty,
                    allowed_methods=("POST",),
                ),
            },
        )

    @property
    def service_name(self):
        return "i2y.connecpy.example.Haberdasher"


class HaberdasherClientSync(ConnecpyClientSync):
    def MakeHat(
        self,
        request: example_dot_haberdasher__pb2.Size,
        *,
        headers: Optional[RequestHeaders] = None,
        timeout_ms: Optional[int] = None,
        server_path_prefix: str = "",
        use_get: bool = False,
    ) -> example_dot_haberdasher__pb2.Hat:
        method = "GET" if use_get else "POST"
        return self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/MakeHat",
            method=method,
            headers=headers,
            timeout_ms=timeout_ms,
            request=request,
            response_class=example_dot_haberdasher__pb2.Hat,
        )

    def DoNothing(
        self,
        request: google_dot_protobuf_dot_empty__pb2.Empty,
        *,
        headers: Optional[RequestHeaders] = None,
        timeout_ms: Optional[int] = None,
        server_path_prefix: str = "",
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        method = "POST"
        return self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/DoNothing",
            method=method,
            headers=headers,
            timeout_ms=timeout_ms,
            request=request,
            response_class=google_dot_protobuf_dot_empty__pb2.Empty,
        )
