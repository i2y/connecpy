# Connecpy

Python implementation of [Connect Protocol](https://connectrpc.com/docs/protocol).

This repo contains a protoc plugin that generates sever and client code and a pypi package with common implementation details.

## Installation

### Requirements

- Python 3.10 or later

### Install the protoc plugin

You can install the protoc plugin using one of these methods:

#### Option 1: Download pre-built binary (recommended)
Download the latest release from [GitHub Releases](https://github.com/i2y/connecpy/releases/latest) page. Pre-built binaries are available for:
- Linux (amd64, arm64)
- macOS (amd64, arm64)
- Windows (amd64, arm64)

#### Option 2: Install with Go
If you have Go installed, you can install using:

```sh
go install github.com/i2y/connecpy/protoc-gen-connecpy@latest
```

### Install the Python package

Additionally, please add the connecpy package to your project using your preferred package manager. For instance, with [uv](https://docs.astral.sh/uv/), use the command:

```sh
uv add connecpy
```

or

```sh
pip install connecpy
```

### Server runtime dependencies

To run the server, you'll need one of the following: [Uvicorn](https://www.uvicorn.org/), [Daphne](https://github.com/django/daphne), or [Hypercorn](https://gitlab.com/pgjones/hypercorn). If your goal is to support both HTTP/1.1 and HTTP/2, you should opt for either Daphne or Hypercorn. Additionally, to test the server, you might need a client command, such as [buf](https://buf.build/docs/installation).

## Generate and run

Use the protoc plugin to generate connecpy server and client code.

```sh
protoc --python_out=./ --pyi_out=./ --connecpy_out=./ ./haberdasher.proto
```

### Server code (ASGI)

```python
# service.py
import random

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.server import ServiceContext

from haberdasher_pb2 import Hat, Size


class HaberdasherService:
    async def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
        print("remaining_time: ", ctx.timeout_ms())
        if req.inches <= 0:
            raise ConnecpyException(
                Code.INVALID_ARGUMENT, "inches: I can't make a hat that small!"
            )
        response = Hat(
            size=req.inches,
            color=random.choice(["white", "black", "brown", "red", "blue"]),
        )
        if random.random() > 0.5:
            response.name = random.choice(
                ["bowler", "baseball cap", "top hat", "derby"]
            )

        return response
```

```python
# server.py
import haberdasher_connecpy
from service import HaberdasherService

app = haberdasher_connecpy.HaberdasherASGIApplication(
    HaberdasherService()
)
```

Run the server with

```sh
uvicorn --port=3000 server:app
```

or

```sh
daphne --port=3000 server:app
```

or

```sh
hypercorn --bind :3000 server:app
```

### Client code (Asyncronous)

```python
# async_client.py
import asyncio

import httpx

from connecpy.exceptions import ConnecpyException

import haberdasher_connecpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


async def main():
    async with httpx.AsyncClient(
        base_url=server_url,
        timeout=timeout_s,
    ) as session:
        async with haberdasher_connecpy.HaberdasherClient(server_url, session=session) as client:

    try:
        response = await client.MakeHat(
            haberdasher_pb2.Size(inches=12),
        )
        if not response.HasField("name"):
            print("We didn't get a name!")
            print(response)
        except ConnecpyException as e:
            print(e.code, e.message)


if __name__ == "__main__":
    asyncio.run(main())
```

Example output :

```
size: 12
color: "black"
name: "bowler"
```

## Client code (Synchronous)

```python
# client.py
from connecpy.exceptions import ConnecpyException

import haberdasher_connecpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


def main():
    with haberdasher_connecpy.HaberdasherClientSync(server_url, timeout_ms=timeout_s * 1000) as client:
        try:
            response = client.MakeHat(
                haberdasher_pb2.Size(inches=12),
            )
            if not response.HasField("name"):
                print("We didn't get a name!")
            print(response)
        except ConnecpyException as e:
            print(e.code, e.message)


if __name__ == "__main__":
    main()
```

### Other clients

Of course, you can use any HTTP client to make requests to a Connecpy server. For example, commands like `curl` or `buf curl` can be used, as well as HTTP client libraries such as `requests`, `httpx`, `aiohttp`, and others. The examples below use `curl` and `buf curl`.

Content-Type: application/proto, HTTP/1.1

```sh
buf curl --data '{"inches": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat --schema ./haberdasher.proto
```

On Windows, Content-Type: application/proto, HTTP/1.1

```sh
buf curl --data '{\"inches\": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat --schema .\haberdasher.proto
```

Content-Type: application/proto, HTTP/2

```sh
buf curl --data '{"inches": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat --http2-prior-knowledge --schema ./haberdasher.proto
```

On Windows, Content-Type: application/proto, HTTP/2

```sh
buf curl --data '{\"inches\": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat --http2-prior-knowledge --schema .\haberdasher.proto
```

Content-Type: application/json, HTTP/1.1

```sh
curl -X POST -H "Content-Type: application/json" -d '{"inches": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat
```

On Windows, Content-Type: application/json, HTTP/1.1

```sh
curl -X POST -H "Content-Type: application/json" -d '{\"inches\": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat
```

Content-Type: application/json, HTTP/2

```sh
curl --http2-prior-knowledge -X POST -H "Content-Type: application/json" -d '{"inches": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat
```

On Windows, Content-Type: application/json, HTTP/2

```sh
curl --http2-prior-knowledge -X POST -H "Content-Type: application/json" -d '{\"inches\": 12}' -v http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat
```

## WSGI Support

Connecpy now provides WSGI support via the `ConnecpyWSGIApp`. This synchronous application adapts our service endpoints to the WSGI specification. It reads requests from the WSGI `environ`, processes POST requests, and returns responses using `start_response`. This enables integration with legacy WSGI servers and middleware.

Please see the example in the [example directory](example/example/wsgi_server.py).

## Compression Support

Connecpy supports various compression methods for both GET and POST requests/responses:

- gzip
- brotli (br)
- zstandard (zstd)
- identity (no compression)

For GET requests, specify the compression method using the `compression` query parameter:

```sh
curl "http://localhost:3000/service/method?compression=gzip&message=..."
```

For POST requests, use the `Content-Encoding` header:

```sh
curl -H "Content-Encoding: br" -d '{"data": "..."}' http://localhost:3000/service/method
```

The compression is handled directly in the request handlers, ensuring consistent behavior across HTTP methods and frameworks (ASGI/WSGI).

With Connecpy's compression features, you can automatically handle compressed requests and responses. Here are some examples:

### Server-side

The compression handling is built into both ASGI and WSGI applications. You don't need any additional middleware configuration - it works out of the box!

### Client-side

For async clients:

```python
async with haberdasher_connecpy.HaberdasherClient(
    server_url,
    send_compression="br",
    accept_compression=["gzip"]
) as client:
    response = await client.MakeHat(
        haberdasher_pb2.Size(inches=12)
    )
```

For synchronous clients:

```python
with haberdasher_connecpy.HaberdasherClientSync(
    server_url,
    send_compression="zstd",  # Use Zstandard compression for request
    accept_compression=["br"]  # Accept Brotli compressed response
) as client:
    response = client.MakeHat(
        haberdasher_pb2.Size(inches=12)
    )
```

Using GET requests with compression:

```python
response = await client.MakeHat(
    haberdasher_pb2.Size(inches=12),
    use_get=True  # Enable GET request (for methods marked with no_side_effects)
)
# Note: Compression for GET requests is handled automatically based on the client's configuration
```

### CORS Support

`ConnecpyASGIApp` is a standard ASGI application meaning any CORS ASGI middleware will work well with it, for example
`starlette.middleware.cors.CORSMiddleware`. Refer to [Connect Docs](https://connectrpc.com/docs/cors/) for standard
headers commonly used by Connect clients for CORS negotiation and a full [example using Starlette](./example/example/starlette_mount.py).

## Connect Protocol

Connecpy protoc plugin generates the code based on [Connect Protocol](https://connectrpc.com/docs/protocol) from the `.proto` files.
Currently, Connecpy supports only Unary RPCs using the POST HTTP method. Connecpy will support other types of RPCs as well, in the near future.

## Proto Editions Support

Starting from version 2.0.0, protoc-gen-connecpy supports Proto Editions 2023. You can use the new editions syntax in your `.proto` files:

```proto
edition = "2023";

package example;

service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
}

message HelloRequest {
  string name = 1;
}

message HelloReply {
  string message = 1;
}
```

The code generation works the same way as with proto2/proto3 syntax. Note that you'll need protoc version 26.0 or later to use editions syntax.

## Misc

### Routing

Connecpy applications are standard WSGI or ASGI applications. For complex routing requirements,
you can use a routing framework such as [werkzeug](./example/example/flask_mount.py) or
[starlette](./example/example/routing_asgi.py).

The generated application classes now expose a `path` property that returns the service's URL path, making it easier to mount multiple services:

```python
haberdasher_app = haberdasher_connecpy.HaberdasherASGIApplication(service)
print(haberdasher_app.path)  # "/package.ServiceName"

# Use with routing frameworks
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app,
    {
        haberdasher_app.path: haberdasher_app,
    },
)
```

### Interceptor (Server Side)

ConnecpyASGIApplication supports interceptors (ASGI only, not available for WSGI). You can add interceptors by passing `interceptors` to the application constructor:

```python
# server.py
from typing import Any, Callable

from connecpy.server import ServerInterceptor, ServiceContext

import haberdasher_connecpy
from service import HaberdasherService


class MyInterceptor(ServerInterceptor):
    def __init__(self, msg):
        self._msg = msg

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: ServiceContext,
        method_name: str,
    ) -> Any:
        print("intercepting " + method_name + " with " + self._msg)
        return await method(request, ctx)


my_interceptor_a = MyInterceptor("A")
my_interceptor_b = MyInterceptor("B")

service = haberdasher_connecpy.HaberdasherASGIApplication(
    HaberdasherService(),
    interceptors=[my_interceptor_a, my_interceptor_b]
)
```

Btw, `ServerInterceptor`'s `intercept` method has compatible signature as `intercept` method of [grpc_interceptor.server.AsyncServerInterceptor](https://grpc-interceptor.readthedocs.io/en/latest/#async-server-interceptors), so you might be able to convert Connecpy interceptors to gRPC interceptors by just changing the import statement and the parent class.

### Message Body Length

Currently, message body length limit is set to 100kb, you can override this by passing `max_receive_message_length` to the application constructor.

```python
# this sets max message length to be 10 bytes
app = HaberedasherASGIApplication(max_receive_message_length=10)

```

## Standing on the shoulders of giants

The initial version (1.0.0) of this software was created by modifying https://github.com/verloop/twirpy at January 4, 2024, so that it supports Connect Protocol.
