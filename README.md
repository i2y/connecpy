# Connecpy

Python implementation of [Connect Protocol](https://connectrpc.com/docs/protocol).

This repo contains a protoc plugin that generates sever and client code and a pypi package with common implementation details.

## Installation

You can install the protoc plugin to generate files by running the command:

```sh
go install github.com/i2y/connecpy/protoc-gen-connecpy@latest
```

Additionally, please add the connecpy package to your project using your preferred package manager. For instance, with [uv](https://docs.astral.sh/uv/), use the command:


```sh
uv add connecpy
```

or

```sh
pip install connecpy
```


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

from connecpy.exceptions import InvalidArgument
from connecpy.context import ServiceContext

from haberdasher_pb2 import Hat, Size


class HaberdasherService(object):
    async def MakeHat(self, req: Size, ctx: ServiceContext) -> Hat:
        print("remaining_time: ", ctx.time_remaining())
        if req.inches <= 0:
            raise InvalidArgument(
                argument="inches", error="I can't make a hat that small!"
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
from connecpy import context
from connecpy.asgi import ConnecpyASGIApp

import haberdasher_connecpy
from service import HaberdasherService

service = haberdasher_connecpy.HaberdasherServer(
    service=HaberdasherService()
)
app = ConnecpyASGIApp()
app.add_service(service)
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

from connecpy.context import ClientContext
from connecpy.exceptions import ConnecpyServerException

import haberdasher_connecpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


async def main():
    session = httpx.AsyncClient(
        base_url=server_url,
        timeout=timeout_s,
    )
    client = haberdasher_connecpy.AsyncHaberdasherClient(server_url, session=session)

    try:
        response = await client.MakeHat(
            ctx=ClientContext(),
            request=haberdasher_pb2.Size(inches=12),
            # Optionally provide a session per request
            # session=session,
        )
        if not response.HasField("name"):
            print("We didn't get a name!")
        print(response)
    except ConnecpyServerException as e:
        print(e.code, e.message, e.to_dict())
    finally:
        # Close the session (could also use a context manager)
        await session.aclose()


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
from connecpy.context import ClientContext
from connecpy.exceptions import ConnecpyServerException

import haberdasher_connecpy, haberdasher_pb2


server_url = "http://localhost:3000"
timeout_s = 5


def main():
    client = haberdasher_connecpy.HaberdasherClient(server_url, timeout=timeout_s)

    try:
        response = client.MakeHat(
            ctx=ClientContext(),
            request=haberdasher_pb2.Size(inches=12),
        )
        if not response.HasField("name"):
            print("We didn't get a name!")
        print(response)
    except ConnecpyServerException as e:
        print(e.code, e.message, e.to_dict())


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

Please see the example in the [example directory](example/wsgi_server.py).

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

For synchronous clients:
```python
from connecpy.context import ClientContext

client = HaberdasherClient(server_url)
response = client.MakeHat(
    ctx=ClientContext(
        headers={
            "Content-Encoding": "br",  # Use Brotli compression for request
            "Accept-Encoding": "gzip",  # Accept gzip compressed response
        }
    ),
    request=request_obj,
)
```

For async clients:
```python
async with httpx.AsyncClient() as session:
    client = AsyncHaberdasherClient(server_url, session=session)
    response = await client.MakeHat(
        ctx=ClientContext(),
        request=request_obj,
        headers={
            "Content-Encoding": "zstd",  # Use Zstandard compression for request
            "Accept-Encoding": "br",     # Accept Brotli compressed response
        },
    )
```

Using GET requests with compression:
```python
response = client.MakeHat(
    ctx=ClientContext(),
    request=request_obj,
    use_get=True,  # Enable GET request (for methods marked with no_side_effects)
    params={
        "compression": "gzip",  # Use gzip compression for the message
    }
)
```

### CORS Support

Connecpy provides built-in CORS support via the `CORSMiddleware`. By default, it allows all origins and includes necessary Connect Protocol headers:

```python
from connecpy.cors import CORSMiddleware

app = ConnecpyASGIApp()
app.add_service(service)
app = CORSMiddleware(app)  # Use default configuration
```

You can customize the CORS behavior using `CORSConfig`:

```python
from connecpy.cors import CORSMiddleware, CORSConfig

config = CORSConfig(
    allow_origin="https://your-domain.com",           # Restrict allowed origins
    allow_methods=("POST", "GET", "OPTIONS"),         # Customize allowed methods
    allow_headers=(                                   # Customize allowed headers
        "Content-Type",
        "Connect-Protocol-Version",
        "X-Custom-Header",
    ),
    access_control_max_age=3600,                     # Set preflight cache duration
)

app = CORSMiddleware(app, config=config)
```

The middleware handles both preflight requests (OPTIONS) and adds appropriate CORS headers to responses.

## Connect Protocol

Connecpy protoc plugin generates the code based on [Connect Protocl](https://connectrpc.com/docs/protocol) from the `.proto` files.
Currently, Connecpy supports only Unary RPCs using the POST HTTP method. Connecpy will support other types of RPCs as well, in the near future.

## Misc

### Server Path Prefix

You can set server path prefix by passing `server_path_prefix` to `ConnecpyASGIApp` constructor.

This example sets server path prefix to `/foo/bar`.
```python
# server.py
service = haberdasher_connecpy.HaberdasherServer(
    service=HaberdasherService(),
    server_path_prefix="/foo/bar",
)
```

```python
# async_client.py
response = await client.MakeHat(
    ctx=ClientContext(),
    request=haberdasher_pb2.Size(inches=12),
    server_path_prefix="/foo/bar",
)
```

### Interceptor (Server Side)

ConnecpyASGIApp supports interceptors. You can add interceptors by passing `interceptors` to `ConnecpyASGIApp` constructor.
AsyncConnecpyServerInterceptor

```python
# server.py
from typing import Any, Callable

from connecpy import context
from connecpy.asgi import ConnecpyASGIApp
from connecpy.interceptor import AsyncConnecpyServerInterceptor

import haberdasher_connecpy
from service import HaberdasherService


class MyInterceptor(AsyncConnecpyServerInterceptor):
    def __init__(self, msg):
        self._msg = msg

    async def intercept(
        self,
        method: Callable,
        request: Any,
        ctx: context.ServiceContext,
        method_name: str,
    ) -> Any:
        print("intercepting " + method_name + " with " + self._msg)
        return await method(request, ctx)


my_interceptor_a = MyInterceptor("A")
my_interceptor_b = MyInterceptor("B")

service = haberdasher_connecpy.HaberdasherServer(service=HaberdasherService())
app = ConnecpyASGIApp(
    interceptors=(my_interceptor_a, my_interceptor_b),
)
app.add_service(service)
```

Btw, `ConnecpyServerInterceptor`'s `intercept` method has compatible signature as `intercept` method of [grpc_interceptor.server.AsyncServerInterceptor](https://grpc-interceptor.readthedocs.io/en/latest/#async-server-interceptors), so you might be able to convert Connecpy interceptors to gRPC interceptors by just changing the import statement and the parent class.


### gRPC Compatibility
In Connecpy, unlike connect-go, it is not possible to simultaneously support both gRPC and Connect RPC on the same server and port. In addition to it, Connecpy itself doesn't support gRPC. However, implementing a gRPC server using the same service code used for Connecpy server is feasible, as shown below. This is possible because the type signature of the service class in Connecpy is compatible with type signature gRPC farmework requires.
The example below uses [grpc.aio](https://grpc.github.io/grpc/python/grpc_asyncio.html) and there are in [example dicrectory](example/README.md).


```python
# grpc_server.py
import asyncio

from grpc.aio import server

import haberdasher_pb2_grpc

# same service.py as the one used in previous server.py
from service import HaberdasherService

host = "localhost:50051"


async def main():
    s = server()
    haberdasher_pb2_grpc.add_HaberdasherServicer_to_server(HaberdasherService(), s)
    bound_port = s.add_insecure_port(host)
    print(f"localhost:{bound_port}")
    await s.start()
    await s.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())
```

```python
# grpc_client.py
import asyncio

from grpc.aio import insecure_channel

import haberdasher_pb2
import haberdasher_pb2_grpc


target = "localhost:50051"


async def main():
    channel = insecure_channel(target)
    stub = haberdasher_pb2_grpc.HaberdasherStub(channel)
    request = haberdasher_pb2.Size(inches=12)
    response = await stub.MakeHat(request)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
```

### Message Body Length

Currently, message body length limit is set to 100kb, you can override this by passing `max_receive_message_length` to `ConnecpyASGIApp` constructor.

```python
# this sets max message length to be 10 bytes
app = ConnecpyASGIApp(max_receive_message_length=10)

```

## Standing on the shoulders of giants

The initial version (1.0.0) of this software was created by modifying https://github.com/verloop/twirpy at January 4, 2024, so that it supports Connect Protocol. Therefore, this software is also licensed under Unlicense same as twirpy.
