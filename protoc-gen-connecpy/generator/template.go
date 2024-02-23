package generator

import "text/template"

type ConnecpyTemplateVariables struct {
	FileName              string
	ModuleName            string
	Services              []*ConnecpyService
}

type ConnecpyService struct {
	ServiceURL string
	Name       string
	Comment    string
	Methods    []*ConnecpyMethod
}

type ConnecpyMethod struct {
	ServiceURL  string
	ServiceName string
	Name        string
	Comment     string
	InputType   string
	OutputType  string
}

type ConnecpyImport struct {
	From   string
	Import string
}

// ConnecpyTemplate - Template for connecpy server and client
var ConnecpyTemplate = template.Must(template.New("ConnecpyTemplate").Parse(`# -*- coding: utf-8 -*-
# Generated by https://github.com/i2y/connecpy/protoc-gen-connecpy.  DO NOT EDIT!
# source: {{.FileName}}

from typing import Protocol, Union

import httpx

from connecpy.async_client import AsyncConnecpyClient
from connecpy.base import Endpoint
from connecpy.server import ConnecpyServer
from connecpy.client import ConnecpyClient
from connecpy.context import ServiceContext

import {{.ModuleName}}_pb2 as _pb2

{{range .Services}}
class {{.Name}}Service(Protocol):{{- range .Methods }}
	async def {{.Name}}(self, req: _pb2.{{.InputType}}, ctx: ServiceContext) -> _pb2.{{.OutputType}}:
		...{{- end }}


class {{.Name}}Server(ConnecpyServer):
	def __init__(self, *, service: {{.Name}}Service, server_path_prefix=""):
		super().__init__(service=service)
		self._prefix = f"{server_path_prefix}/{{.ServiceURL}}"
		self._endpoints = { {{- range .Methods }}
			"{{.Name}}": Endpoint[_pb2.{{.InputType}}, _pb2.{{.OutputType}}](
				service_name="{{.ServiceName}}",
				name="{{.Name}}",
				function=getattr(service, "{{.Name}}"),
				input=_pb2.{{.InputType}},
				output=_pb2.{{.OutputType}},
			),{{- end }}
		}


class {{.Name}}Client(ConnecpyClient):{{range .Methods}}
	def {{.Name}}(
		self,
		*,
		request,
		ctx,
		server_path_prefix="",
		**kwargs,
	):
		return self._make_request(
			url=f"{server_path_prefix}/{{.ServiceURL}}/{{.Name}}",
			ctx=ctx,
			request=request,
			response_obj=_pb2.{{.OutputType}},
			**kwargs,
		){{end}}


class Async{{.Name}}Client(AsyncConnecpyClient):{{range .Methods}}
	async def {{.Name}}(
        self,
        *,
        request,
        ctx,
        server_path_prefix="",
        session: Union[httpx.AsyncClient, None] = None,
        **kwargs,
    ):
		return await self._make_request(
			url=f"{server_path_prefix}/{{.ServiceURL}}/{{.Name}}",
			ctx=ctx,
			request=request,
			response_obj=_pb2.{{.OutputType}},
			session=session,
			**kwargs,
		)
{{end}}{{end}}`))
