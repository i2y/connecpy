package generator

import "text/template"

type ConnecpyTemplateVariables struct {
	FileName   string
	ModuleName string
	Services   []*ConnecpyService
}

type ConnecpyService struct {
	Package string
	Name    string
	Comment string
	Methods []*ConnecpyMethod
}

type ConnecpyMethod struct {
	Package               string
	ServiceName           string
	Name                  string
	Comment               string
	InputType             string
	InputTypeForProtocol  string
	OutputType            string
	OutputTypeForProtocol string
	NoSideEffects         bool
}

// ConnecpyTemplate - Template for connecpy server and client
var ConnecpyTemplate = template.Must(template.New("ConnecpyTemplate").Parse(`# -*- coding: utf-8 -*-
# Generated by https://github.com/i2y/connecpy/protoc-gen-connecpy.  DO NOT EDIT!
# source: {{.FileName}}
{{if .Services}}
from typing import Optional, Protocol, Union

import httpx

from connecpy.async_client import AsyncConnecpyClient
from connecpy.base import Endpoint
from connecpy.server import ConnecpyServer
from connecpy.client import ConnecpyClient
from connecpy.context import ClientContext, ServiceContext

import {{.ModuleName}}_pb2 as _pb2
{{- end}}
{{- range .Services}}


class {{.Name}}(Protocol):{{- range .Methods }}
    async def {{.Name}}(self, req: {{.InputTypeForProtocol}}, ctx: ServiceContext) -> {{.OutputTypeForProtocol}}: ...
{{- end }}


class {{.Name}}Server(ConnecpyServer):
    def __init__(self, *, service: {{.Name}}, server_path_prefix=""):
        super().__init__()
        self._prefix = f"{server_path_prefix}/{{.Package}}.{{.Name}}"
        self._endpoints = { {{- range .Methods }}
            "{{.Name}}": Endpoint[{{.InputType}}, {{.OutputType}}](
                service_name="{{.ServiceName}}",
                name="{{.Name}}",
                function=getattr(service, "{{.Name}}"),
                input={{.InputType}},
                output={{.OutputType}},
                allowed_methods={{if .NoSideEffects}}("GET", "POST"){{else}}("POST",){{end}},
            ),{{- end }}
        }

    def serviceName(self):
        return "{{.Package}}.{{.Name}}"
{{- end }}

{{range .Services}}
class {{.Name}}Sync(Protocol):{{- range .Methods }}
    def {{.Name}}(self, req: {{.InputTypeForProtocol}}, ctx: ServiceContext) -> {{.OutputTypeForProtocol}}: ...
{{- end }}


class {{.Name}}ServerSync(ConnecpyServer):
    def __init__(self, *, service: {{.Name}}Sync, server_path_prefix=""):
        super().__init__()
        self._prefix = f"{server_path_prefix}/{{.Package}}.{{.Name}}"
        self._endpoints = { {{- range .Methods }}
            "{{.Name}}": Endpoint[{{.InputType}}, {{.OutputType}}](
                service_name="{{.ServiceName}}",
                name="{{.Name}}",
                function=getattr(service, "{{.Name}}"),
                input={{.InputType}},
                output={{.OutputType}},
                allowed_methods={{if .NoSideEffects}}("GET", "POST"){{else}}("POST",){{end}},
            ),{{- end }}
        }

    def serviceName(self):
        return "{{.Package}}.{{.Name}}"


class {{.Name}}Client(ConnecpyClient):{{range .Methods}}
    def {{.Name}}(
        self,
        *,
        request: {{.InputTypeForProtocol}},
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        {{if .NoSideEffects}}use_get: bool = False,
        **kwargs,
        {{- else}}**kwargs,{{end}}
    ) -> {{.OutputTypeForProtocol}}:
        {{if .NoSideEffects}}method = "GET" if use_get else "POST"{{else}}method = "POST"{{end}}
        return self._make_request(
            url=f"{server_path_prefix}/{{.Package}}.{{.ServiceName}}/{{.Name}}",
            ctx=ctx,
            request=request,
            response_class={{.OutputType}},
            method=method,
            **kwargs,
        )
{{end}}

class Async{{.Name}}Client(AsyncConnecpyClient):{{range .Methods}}
    async def {{.Name}}(
        self,
        *,
        request: {{.InputTypeForProtocol}},
        ctx: Optional[ClientContext] = None,
        server_path_prefix: str = "",
        session: Union[httpx.AsyncClient, None] = None,
        {{if .NoSideEffects}}use_get: bool = False,
        **kwargs,
        {{- else}}**kwargs,{{end}}
    ) -> {{.OutputTypeForProtocol}}:
        {{if .NoSideEffects}}method = "GET" if use_get else "POST"{{else}}method = "POST"{{end}}
        return await self._make_request(
            url=f"{server_path_prefix}/{{.Package}}.{{.ServiceName}}/{{.Name}}",
            ctx=ctx,
            request=request,
            response_class={{.OutputType}},
            method=method,
            session=session,
            **kwargs,
        )
{{end}}{{end}}`))
