# -*- coding: utf-8 -*-
# Generated by https://github.com/i2y/connecpy/protoc-gen-connecpy.  DO NOT EDIT!
# source: haberdasher.proto

from typing import Optional, Protocol, Union

import httpx

from connecpy.async_client import AsyncConnecpyClient
from connecpy.base import Endpoint
from connecpy.server import ConnecpyServer
from connecpy.client import ConnecpyClient
from connecpy.context import ClientContext, ServiceContext
import google.protobuf.empty_pb2 as google_dot_protobuf_dot_empty__pb2
import haberdasher_pb2 as haberdasher__pb2


class Haberdasher(Protocol):
    async def MakeHat(
        self, req: haberdasher__pb2.Size, ctx: ServiceContext
    ) -> haberdasher__pb2.Hat: ...
    async def DoNothing(
        self, req: google_dot_protobuf_dot_empty__pb2.Empty, ctx: ServiceContext
    ) -> google_dot_protobuf_dot_empty__pb2.Empty: ...


class HaberdasherServer(ConnecpyServer):
    def __init__(self, *, service: Haberdasher, server_path_prefix=""):
        super().__init__()
        self._prefix = f"{server_path_prefix}/i2y.connecpy.example.Haberdasher"
        self._endpoints = {
            "MakeHat": Endpoint[haberdasher__pb2.Size, haberdasher__pb2.Hat](
                service_name="Haberdasher",
                name="MakeHat",
                function=getattr(service, "MakeHat"),
                input=haberdasher__pb2.Size,
                output=haberdasher__pb2.Hat,
                allowed_methods=("GET", "POST"),
            ),
            "DoNothing": Endpoint[
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
        }

    def serviceName(self):
        return "i2y.connecpy.example.Haberdasher"


class HaberdasherSync(Protocol):
    def MakeHat(
        self, req: haberdasher__pb2.Size, ctx: ServiceContext
    ) -> haberdasher__pb2.Hat: ...
    def DoNothing(
        self, req: google_dot_protobuf_dot_empty__pb2.Empty, ctx: ServiceContext
    ) -> google_dot_protobuf_dot_empty__pb2.Empty: ...


class HaberdasherServerSync(ConnecpyServer):
    def __init__(self, *, service: HaberdasherSync, server_path_prefix=""):
        super().__init__()
        self._prefix = f"{server_path_prefix}/i2y.connecpy.example.Haberdasher"
        self._endpoints = {
            "MakeHat": Endpoint[haberdasher__pb2.Size, haberdasher__pb2.Hat](
                service_name="Haberdasher",
                name="MakeHat",
                function=getattr(service, "MakeHat"),
                input=haberdasher__pb2.Size,
                output=haberdasher__pb2.Hat,
                allowed_methods=("GET", "POST"),
            ),
            "DoNothing": Endpoint[
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
        }

    def serviceName(self):
        return "i2y.connecpy.example.Haberdasher"


class HaberdasherClient(ConnecpyClient):
    def MakeHat(
        self,
        request: haberdasher__pb2.Size,
        *,
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        use_get: bool = False,
        **kwargs,
    ) -> haberdasher__pb2.Hat:
        method = "GET" if use_get else "POST"
        return self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/MakeHat",
            ctx=ctx,
            request=request,
            response_class=haberdasher__pb2.Hat,
            method=method,
            **kwargs,
        )

    def DoNothing(
        self,
        request: google_dot_protobuf_dot_empty__pb2.Empty,
        *,
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        **kwargs,
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        method = "POST"
        return self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/DoNothing",
            ctx=ctx,
            request=request,
            response_class=google_dot_protobuf_dot_empty__pb2.Empty,
            method=method,
            **kwargs,
        )


class AsyncHaberdasherClient(AsyncConnecpyClient):
    async def MakeHat(
        self,
        request: haberdasher__pb2.Size,
        *,
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        session: Union[httpx.AsyncClient, None] = None,
        use_get: bool = False,
        **kwargs,
    ) -> haberdasher__pb2.Hat:
        method = "GET" if use_get else "POST"
        return await self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/MakeHat",
            ctx=ctx,
            request=request,
            response_class=haberdasher__pb2.Hat,
            method=method,
            session=session,
            **kwargs,
        )

    async def DoNothing(
        self,
        request: google_dot_protobuf_dot_empty__pb2.Empty,
        *,
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        session: Union[httpx.AsyncClient, None] = None,
        **kwargs,
    ) -> google_dot_protobuf_dot_empty__pb2.Empty:
        method = "POST"
        return await self._make_request(
            url=f"{server_path_prefix}/i2y.connecpy.example.Haberdasher/DoNothing",
            ctx=ctx,
            request=request,
            response_class=google_dot_protobuf_dot_empty__pb2.Empty,
            method=method,
            session=session,
            **kwargs,
        )
