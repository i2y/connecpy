# Connecpy

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/i2y/connecpy/actions/workflows/ci.yaml/badge.svg)](https://github.com/i2y/connecpy/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/i2y/connecpy/graph/badge.svg)](https://codecov.io/github/i2y/connecpy)
[![PyPI version](https://img.shields.io/pypi/v/connecpy)](https://pypi.org/project/connecpy)

Python implementation of [Connect Protocol](https://connectrpc.com/docs/protocol).

This repo contains a protoc plugin that generates sever and client code and a pypi package with common implementation details.

## Installation

### Requirements

- Python 3.10 or later

### Install the protoc plugin

You can install the protoc plugin using one of these methods:

#### Option 1: Quick Install (Linux/macOS) - Recommended

Install with a single command:

```bash
curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | bash
```

You can customize the installation with environment variables:

```bash
# Install to a custom directory
curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | PROTOC_GEN_CONNECPY_INSTALL=$HOME/.local/bin bash

# Install a specific version
curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | VERSION=v2.2.0 bash

# Combine multiple options
curl -sSL https://raw.githubusercontent.com/i2y/connecpy/main/install.sh | PROTOC_GEN_CONNECPY_INSTALL=$HOME/.local/bin VERSION=v2.2.0 bash
```

#### Option 2: Manual Download

1. **Download the appropriate archive for your platform** from [GitHub Releases](https://github.com/i2y/connecpy/releases/latest):
   - **Linux AMD64**: `protoc-gen-connecpy_VERSION_linux_amd64.tar.gz`
   - **Linux ARM64**: `protoc-gen-connecpy_VERSION_linux_arm64.tar.gz`
   - **macOS Intel**: `protoc-gen-connecpy_VERSION_darwin_amd64.tar.gz`
   - **macOS Apple Silicon**: `protoc-gen-connecpy_VERSION_darwin_arm64.tar.gz`
   - **Windows AMD64**: `protoc-gen-connecpy_VERSION_windows_amd64.zip`
   - **Windows ARM64**: `protoc-gen-connecpy_VERSION_windows_arm64.zip`

2. **Extract and install the binary:**

   **Linux/macOS:**
   ```bash
   # Extract the archive
   tar -xzf protoc-gen-connecpy_*.tar.gz
   
   # Make executable (if needed)
   chmod +x protoc-gen-connecpy
   
   # Move to a directory in PATH
   sudo mv protoc-gen-connecpy /usr/local/bin/
   # Or for user-only installation:
   # mkdir -p ~/.local/bin
   # mv protoc-gen-connecpy ~/.local/bin/
   # Make sure ~/.local/bin is in your PATH
   ```

   **Windows (PowerShell):**
   ```powershell
   # Extract the archive
   Expand-Archive protoc-gen-connecpy_*.zip -DestinationPath .
   
   # Move to a directory in PATH, for example:
   Move-Item protoc-gen-connecpy.exe C:\Tools\
   # Then add C:\Tools to your PATH environment variable:
   # [System.Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\Tools", "User")
   ```

3. **Verify installation:**
   ```bash
   # Check if the plugin is accessible
   which protoc-gen-connecpy  # Linux/macOS
   where protoc-gen-connecpy  # Windows
   
   # Test with protoc (requires a .proto file)
   protoc --connecpy_out=. --connecpy_opt=paths=source_relative test.proto
   ```

#### Option 3: Install with Go
If you have Go installed, you can install the plugin directly:

```sh
go install github.com/i2y/connecpy/v2/protoc-gen-connecpy@latest
```

This will install the binary to `$GOPATH/bin` (or `$HOME/go/bin` if GOPATH is not set). Make sure this directory is in your PATH.

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

### Using Buf (v2) - Recommended

Create a `buf.gen.yaml` file:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: gen
  - remote: buf.build/protocolbuffers/pyi
    out: gen
  - local: protoc-gen-connecpy
    out: gen
    # Optional: Enable experimental Transport API
    # opt:
    #   - transport_api=true
```

Then run:

```sh
buf generate
```

### Using protoc directly

```sh
protoc --python_out=./ --pyi_out=./ --connecpy_out=./ ./haberdasher.proto
```

### Generator Options

By default, naming follows PEP8 conventions. To use Google conventions, matching the output of grpc-python, add `--connecpy_opt=naming=google`.
By default, imports are generated absolutely based on the proto package name. To use relative import, add `--connecpy_opt=imports=relative`.

For experimental Transport API support (see Transport API section below), add `--connecpy_opt=transport_api=true`:
```sh
protoc --python_out=./ --pyi_out=./ --connecpy_out=./ --connecpy_opt=transport_api=true ./haberdasher.proto
```

### Server code (ASGI)

```python
# service.py
import random

from connecpy.code import Code
from connecpy.exceptions import ConnecpyException
from connecpy.request import RequestContext

from haberdasher_pb2 import Hat, Size


class HaberdasherService:
    async def make_hat(self, req: Size, ctx: RequestContext) -> Hat:
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
from haberdasher_connecpy import HaberdasherASGIApplication
from service import HaberdasherService

app = HaberdasherASGIApplication(
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

from haberdasher_connecpy import HaberdasherClient
from haberdasher_pb2 import Size, Hat


server_url = "http://localhost:3000"
timeout_s = 5


async def main():
    async with httpx.AsyncClient(
        base_url=server_url,
        timeout=timeout_s,
    ) as session:
        async with HaberdasherClient(server_url, session=session) as client:
            try:
                response = await client.make_hat(
                    Size(inches=12),
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

### Client code (Synchronous)

```python
# client.py
from connecpy.exceptions import ConnecpyException

from haberdasher_connecpy import HaberdasherClientSync
from haberdasher_pb2 import Size, Hat


server_url = "http://localhost:3000"
timeout_s = 5


def main():
    with HaberdasherClientSync(server_url, timeout_ms=timeout_s * 1000) as client:
        try:
            response = client.make_hat(
                Size(inches=12),
            )
            if not response.HasField("name"):
                print("We didn't get a name!")
            print(response)
        except ConnecpyException as e:
            print(e.code, e.message)


if __name__ == "__main__":
    main()
```

## Streaming RPCs

Connecpy supports streaming RPCs in addition to unary RPCs. Here are examples of each type:

### Server Streaming RPC

In server streaming RPCs, the client sends a single request and receives multiple responses from the server.

#### Server implementation

```python
# service.py
from typing import AsyncIterator
from connecpy.request import RequestContext
from haberdasher_pb2 import Hat, Size

class HaberdasherService:
    async def make_similar_hats(self, req: Size, ctx: RequestContext) -> AsyncIterator[Hat]:
        """Server Streaming: Returns multiple hats of similar size"""
        for i in range(3):
            yield Hat(
                size=req.inches + i,
                color=["red", "green", "blue"][i],
                name=f"hat #{i+1}"
            )
```

#### Client implementation (Async)

```python
# async_client.py
import asyncio
import httpx
from connecpy.exceptions import ConnecpyException
from haberdasher_connecpy import HaberdasherClient
from haberdasher_pb2 import Size, Hat

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:3000") as session:
        async with HaberdasherClient(
            "http://localhost:3000",
            session=session
        ) as client:
            # Server streaming: receive multiple responses
            hats = []
            stream = client.make_similar_hats(
                Size(inches=12, description="summer hat")
            )
            async for hat in stream:
                print(f"Received: {hat.color} {hat.name} (size {hat.size})")
                hats.append(hat)
            print(f"Total hats received: {len(hats)}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Client implementation (Sync)

```python
# sync_client.py
import httpx
from connecpy.exceptions import ConnecpyException
from haberdasher_connecpy import HaberdasherClientSync
from haberdasher_pb2 import Size, Hat

def main():
    with httpx.Client(base_url="http://localhost:3000") as session:
        with HaberdasherClientSync(
            "http://localhost:3000",
            session=session
        ) as client:
            # Server streaming: receive multiple responses
            hats = []
            stream = client.make_similar_hats(
                Size(inches=12, description="winter hat")
            )
            for hat in stream:
                print(f"Received: {hat.color} {hat.name} (size {hat.size})")
                hats.append(hat)
            print(f"Total hats received: {len(hats)}")

if __name__ == "__main__":
    main()
```

### Client Streaming RPC

In client streaming RPCs, the client sends multiple requests and receives a single response from the server.

#### Proto definition example

```proto
service ExampleService {
  rpc CollectSizes(stream Size) returns (Summary);
}

message Summary {
  int32 total_count = 1;
  float average_size = 2;
}
```

#### Server implementation

```python
# service.py
from typing import AsyncIterator
from connecpy.request import RequestContext
from example_pb2 import Size, Summary

class ExampleService:
    async def collect_sizes(
        self,
        req: AsyncIterator[Size],
        ctx: RequestContext
    ) -> Summary:
        """Client Streaming: Collect multiple sizes and return summary"""
        sizes = []
        async for size_msg in req:
            sizes.append(size_msg.inches)

        if not sizes:
            return Summary(total_count=0, average_size=0)

        return Summary(
            total_count=len(sizes),
            average_size=sum(sizes) / len(sizes)
        )
```

#### Client implementation (Async)

```python
# async_client.py
import asyncio
from typing import AsyncIterator
import haberdasher_pb2
from haberdasher_connecpy import ExampleClient

async def send_sizes() -> AsyncIterator[haberdasher_pb2.Size]:
    """Generator to send multiple sizes to the server"""
    sizes_to_send = [10, 12, 14, 16, 18]
    for size in sizes_to_send:
        yield haberdasher_pb2.Size(inches=size)
        await asyncio.sleep(0.1)  # Simulate some delay

async def main():
    async with ExampleClient(
        "http://localhost:3000",
        session=session
    ) as client:
        # Client streaming: send multiple requests
        summary = await client.collect_sizes(send_sizes())
        print(f"Summary: {summary.total_count} sizes, average: {summary.average_size}")
```

#### Client implementation (Sync)

```python
# sync_client.py
from typing import Iterator
import haberdasher_pb2
from haberdasher_connecpy import ExampleClientSync

def send_sizes() -> Iterator[haberdasher_pb2.Size]:
    """Generator to send multiple sizes to the server"""
    sizes_to_send = [10, 12, 14, 16, 18]
    for size in sizes_to_send:
        yield haberdasher_pb2.Size(inches=size)

def main():
    with ExampleClientSync(
        "http://localhost:3000",
        session=session
    ) as client:
        # Client streaming: send multiple requests
        summary = client.collect_sizes(send_sizes())
        print(f"Summary: {summary.total_count} sizes, average: {summary.average_size}")
```

### Bidirectional Streaming RPC

Bidirectional streaming RPCs allow both client and server to send multiple messages to each other. Connecpy supports both:

- **Full-duplex bidirectional streaming**: Client and server can send and receive messages simultaneously
- **Half-duplex bidirectional streaming**: Client finishes sending all requests before the server starts sending responses

### Important Notes on Streaming

1. **Server Implementation**:

   - **HTTP/2 ASGI servers** (hypercorn, daphne): Support all streaming types including full-duplex bidirectional streaming
   - **HTTP/1 ASGI/WSGI servers**: Support unary, server streaming, client streaming, and half-duplex bidirectional streaming
   - **Note**: Full-duplex bidirectional streaming is not supported by WSGI servers due to protocol limitations (WSGI servers read the entire request before processing)

2. **Client Support**:

   - Both `ConnecpyClient` (async) and `ConnecpyClientSync` support receiving streaming responses
   - Both support sending streaming requests (client streaming)

3. **Resource Management**: When using streaming responses, resource will be cleaned up when the returned iterator completes or is garbage collected.

4. **Error Handling**: Streaming RPCs can raise exceptions during iteration:

   ```python
   # Async version
   try:
       async for message in stream:
           process(message)
   except ConnecpyException as e:
       print(f"Stream error: {e.code} - {e.message}")

   # Sync version
   try:
       for message in stream:
           process(message)
   except ConnecpyException as e:
       print(f"Stream error: {e.code} - {e.message}")
   ```

5. **Bidirectional Streaming**:
   - Both full-duplex and half-duplex modes are supported
   - In full-duplex mode, client and server can send/receive messages simultaneously
   - In half-duplex mode, client must finish sending before server starts responding

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

## Transport API (Experimental)

The Transport API provides a protocol-agnostic way to create RPC clients that can work with both Connect and gRPC protocols. This allows you to switch between protocols without changing your client code.

**Note**: This feature must be explicitly enabled during code generation using the `transport_api=true` option (see Generator Options above).

### Features

- **Protocol Agnostic**: Write client code once, use with both Connect and gRPC
- **Type Safety**: Generated Protocol types ensure type-safe client interfaces
- **Seamless Integration**: Factory functions automatically handle protocol differences

### Usage

The protoc-gen-connecpy plugin automatically generates Transport API support alongside regular client code:

```python
# Using Connect transport
from connecpy.transport import ConnectTransportAsync
from example.haberdasher_connecpy import create_client
from example.haberdasher_pb2 import Size

async def connect_example():
    transport = ConnectTransportAsync("http://localhost:3000", proto_json=True)
    client = create_client(transport)
    
    hat = await client.make_hat(Size(inches=12))
    print(f"Got hat: {hat.color}")

# Using gRPC transport (requires grpcio)
from connecpy.transport import GrpcTransportAsync

async def grpc_example():
    transport = GrpcTransportAsync("localhost:50051")
    client = create_client(transport)
    
    hat = await client.make_hat(Size(inches=12))
    print(f"Got hat: {hat.color}")
```

### Synchronous API

The Transport API also supports synchronous clients:

```python
from connecpy.transport import ConnectTransport, GrpcTransport
from example.haberdasher_connecpy import create_client_sync

# Connect transport (sync)
transport = ConnectTransport("http://localhost:3000")
client = create_client_sync(transport)
hat = client.make_hat(Size(inches=12))

# gRPC transport (sync)
transport = GrpcTransport("localhost:50051")
client = create_client_sync(transport)
hat = client.make_hat(Size(inches=12))
```

### Advanced Configuration

Both transports support advanced configuration options:

```python
# Connect with compression and custom headers
transport = ConnectTransportAsync(
    "http://localhost:3000",
    proto_json=True,
    accept_compression=["gzip", "br"],
    send_compression="gzip",
    timeout_ms=5000,
)

# gRPC with TLS
import grpc
credentials = grpc.ssl_channel_credentials()
transport = GrpcTransportAsync(
    "api.example.com:443",
    credentials=credentials,
    options=[("grpc.max_receive_message_length", 10000000)],
)
```

**Note**: The Transport API is experimental and the interface may change in future versions. For production use, consider using the standard `HaberdasherClient` and `HaberdasherClientSync` classes directly.

## WSGI Support

Connecpy provides full WSGI support via the `ConnecpyWSGIApplication`. This synchronous application adapts our service endpoints to the WSGI specification. It reads requests from the WSGI `environ`, processes requests, and returns responses using `start_response`. This enables integration with WSGI servers and middleware.

### WSGI Streaming Support

Starting from version 2.1.0, WSGI applications now support streaming RPCs! This includes server streaming, client streaming, and half-duplex bidirectional streaming. Here's how to implement streaming with WSGI:

```python
# service_sync.py
from typing import Iterator
from connecpy.request import RequestContext
from haberdasher_pb2 import Hat, Size

class HaberdasherServiceSync:
    def make_hat(self, req: Size, ctx: RequestContext) -> Hat:
        """Unary RPC"""
        return Hat(size=req.inches, color="red", name="fedora")

    def make_similar_hats(self, req: Size, ctx: RequestContext) -> Iterator[Hat]:
        """Server Streaming RPC - returns multiple hats"""
        for i in range(3):
            yield Hat(
                size=req.inches + i,
                color=["red", "green", "blue"][i],
                name=f"hat #{i+1}"
            )

    def collect_sizes(self, req: Iterator[Size], ctx: RequestContext) -> Hat:
        """Client Streaming RPC - receives multiple sizes, returns one hat"""
        sizes = []
        for size_msg in req:
            sizes.append(size_msg.inches)

        avg_size = sum(sizes) / len(sizes) if sizes else 0
        return Hat(size=int(avg_size), color="average", name="custom")

    def make_various_hats(self, req: Iterator[Size], ctx: RequestContext) -> Iterator[Hat]:
        """Bidirectional Streaming RPC (half-duplex only for WSGI)"""
        # Note: In WSGI, all requests are received before sending responses
        for size_msg in req:
            yield Hat(size=size_msg.inches, color="custom", name=f"size-{size_msg.inches}")
```

```python
# wsgi_server.py
from haberdasher_connecpy import HaberdasherWSGIApplication
from service_sync import HaberdasherServiceSync

app = HaberdasherWSGIApplication(
    HaberdasherServiceSync()
)

if __name__ == "__main__":
    from werkzeug.serving import run_simple
    run_simple("localhost", 3000, app)
```

Please see the complete example in the [example directory](example/example/wsgi_server.py).

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
from haberdasher_connecpy import HaberdasherClient
from haberdasher_pb2 import Size

async with HaberdasherClient(
    server_url,
    send_compression="br",
    accept_compression=["gzip"]
) as client:
    response = await client.make_hat(
        Size(inches=12)
    )
```

For synchronous clients:

```python
from haberdasher_connecpy import HaberdasherClientSync
from haberdasher_pb2 import Size

with HaberdasherClientSync(
    server_url,
    send_compression="zstd",  # Use Zstandard compression for request
    accept_compression=["br"]  # Accept Brotli compressed response
) as client:
    response = client.make_hat(
        Size(inches=12)
    )
```

### Connect GET Support

Connecpy automatically enables GET request support for methods marked with `idempotency_level = NO_SIDE_EFFECTS` in your proto files. This follows the [Connect Protocol's GET specification](https://connectrpc.com/docs/protocol#unary-get-request).

#### Proto Definition

Mark methods as side-effect-free in your `.proto` file:

```proto
service Haberdasher {
  // This method will support both GET and POST requests
  rpc MakeHat(Size) returns (Hat) {
    option idempotency_level = NO_SIDE_EFFECTS;
  }

  // This method only supports POST requests (default)
  rpc UpdateHat(Hat) returns (Hat);
}
```

#### Using GET Requests from Clients

When a method is marked with `NO_SIDE_EFFECTS`, the generated client code includes a `use_get` parameter:

```python
from haberdasher_connecpy import HaberdasherClient, HaberdasherClientSync
from haberdasher_pb2 import Size

# Async client using GET request
async with HaberdasherClient(server_url, session=session) as client:
    response = await client.make_hat(
        Size(inches=12),
        use_get=True  # Use GET instead of POST
    )

# Sync client using GET request
with HaberdasherClientSync(server_url) as client:
    response = client.make_hat(
        Size(inches=12),
        use_get=True  # Use GET instead of POST
    )
```

#### Server-Side Implementation

The generated server code automatically configures GET support based on the proto definition. Methods with `NO_SIDE_EFFECTS` will have `allowed_methods=("GET", "POST")` while others will have `allowed_methods=("POST",)` only.

#### Manual GET Requests

You can also make GET requests directly using curl or other HTTP clients:

```sh
# GET request with query parameters (base64-encoded message)
curl "http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat?encoding=proto&message=CgwI..."

# GET request with compression
curl "http://localhost:3000/i2y.connecpy.example.Haberdasher/MakeHat?encoding=proto&compression=gzip&message=..."
```

Note: GET support is particularly useful for:

- Cacheable operations
- Browser-friendly APIs
- Read-only operations that don't modify server state

### CORS Support

`ConnecpyASGIApp` is a standard ASGI application meaning any CORS ASGI middleware will work well with it, for example
`starlette.middleware.cors.CORSMiddleware`. Refer to [Connect Docs](https://connectrpc.com/docs/cors/) for standard
headers commonly used by Connect clients for CORS negotiation and a full [example using Starlette](./example/example/starlette_mount.py).

## Connect Protocol

Connecpy protoc plugin generates the code based on [Connect Protocol](https://connectrpc.com/docs/protocol) from the `.proto` files.

### Supported RPC Types

Connecpy supports the following RPC types:

- **Unary RPCs** - Single request/response
- **Server Streaming RPCs** - Single request, multiple responses
- **Client Streaming RPCs** - Multiple requests, single response
- **Bidirectional Streaming RPCs** - Multiple requests and responses (both full-duplex and half-duplex)

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
from haberdasher_connecpy import HaberdasherWSGIApplication

haberdasher_app = HaberdasherWSGIApplication(service)
print(haberdasher_app.path)  # "/package.ServiceName"

# Use with routing frameworks
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app,
    {
        haberdasher_app.path: haberdasher_app,
    },
)
```

### Server-Side Interceptors

Connecpy supports server-side interceptors for both ASGI and WSGI applications. Interceptors allow you to add cross-cutting concerns like logging, authentication, and metrics to your services.

#### Type-Safe Interceptors

Connecpy provides type-safe interceptors for each RPC type:

```python
# server.py
from typing import Awaitable, Callable, AsyncIterator
from connecpy.request import RequestContext
from haberdasher_pb2 import Size, Hat
from haberdasher_connecpy import HaberdasherASGIApplication
from service import HaberdasherService

# Single interceptor class handling multiple RPC types
class LoggingInterceptor:
    async def intercept_unary(
        self,
        next: Callable[[Size, RequestContext], Awaitable[Hat]],
        request: Size,
        ctx: RequestContext,
    ) -> Hat:
        print(f"Unary RPC: {ctx.method().name}, size={request.inches}")
        response = await next(request, ctx)
        print(f"Response sent: {response.color} hat")
        return response

    async def intercept_server_stream(
        self,
        next: Callable[[Size, RequestContext], AsyncIterator[Hat]],
        request: Size,
        ctx: RequestContext,
    ) -> AsyncIterator[Hat]:
        print(f"Server streaming RPC: {ctx.method().name}, size={request.inches}")
        async for response in next(request, ctx):
            print(f"Streaming: {response.color} hat (size {response.size})")
            yield response

# ASGI application with interceptors
app = HaberdasherASGIApplication(
    HaberdasherService(),
    interceptors=[LoggingInterceptor()]  # Single interceptor handles both unary and streaming
)
```

#### Metadata Interceptors

For simple cross-cutting concerns that don't need access to request/response bodies, use `MetadataInterceptor`:

```python
import time
from connecpy.interceptor import MetadataInterceptor

# Simple timing interceptor
class TimingInterceptor(MetadataInterceptor[float]):
    async def on_start(self, ctx: RequestContext) -> float:
        print(f"Starting {ctx.method().name}")
        return time.time()

    async def on_end(self, start_time: float, ctx: RequestContext) -> None:
        elapsed = time.time() - start_time
        print(f"{ctx.method().name} took {elapsed:.3f}s")

# Works with all RPC types!
app = HaberdasherASGIApplication(
    HaberdasherService(),
    interceptors=[TimingInterceptor()]
)
```

#### Synchronous Interceptors (WSGI)

WSGI applications support synchronous interceptors:

```python
from typing import Callable
from connecpy.interceptor import MetadataInterceptorSync
from connecpy.request import RequestContext
from haberdasher_pb2 import Size, Hat
from haberdasher_connecpy import HaberdasherWSGIApplication

class LoggingInterceptorSync:
    def intercept_unary_sync(
        self,
        next: Callable[[Size, RequestContext], Hat],
        request: Size,
        ctx: RequestContext,
    ) -> Hat:
        print(f"Sync RPC: {ctx.method().name}, size={request.inches}")
        return next(request, ctx)

class TimingInterceptorSync(MetadataInterceptorSync[float]):
    def on_start_sync(self, ctx: RequestContext) -> float:
        return time.time()

    def on_end_sync(self, start_time: float, ctx: RequestContext) -> None:
        elapsed = time.time() - start_time
        print(f"{ctx.method().name} took {elapsed:.3f}s")

# WSGI application with interceptors
wsgi_app = HaberdasherWSGIApplication(
    HaberdasherServiceSync(),
    interceptors=[LoggingInterceptorSync(), TimingInterceptorSync()]
)
```

#### Available Interceptor Types

| Interceptor Type                                          | Use Case                      | ASGI | WSGI |
| --------------------------------------------------------- | ----------------------------- | ---- | ---- |
| `UnaryInterceptor` / `UnaryInterceptorSync`               | Unary RPCs                    | ✅   | ✅   |
| `ClientStreamInterceptor` / `ClientStreamInterceptorSync` | Client streaming RPCs         | ✅   | ✅   |
| `ServerStreamInterceptor` / `ServerStreamInterceptorSync` | Server streaming RPCs         | ✅   | ✅   |
| `BidiStreamInterceptor` / `BidiStreamInterceptorSync`     | Bidirectional streaming RPCs  | ✅   | ✅   |
| `MetadataInterceptor` / `MetadataInterceptorSync`         | All RPC types (metadata only) | ✅   | ✅   |

#### Interceptor Execution Order

Interceptors are executed in the order they are provided. For example, if you provide `[A, B, C]`, the execution order will be:

- A.on_start → B.on_start → C.on_start → handler → C.on_end → B.on_end → A.on_end

### Client-Side Interceptors

Connecpy supports client-side interceptors, allowing you to add cross-cutting concerns to your client requests:

```python
# async_client_with_interceptor.py
import asyncio
from connecpy.exceptions import ConnecpyException
from haberdasher_connecpy import HaberdasherClient
from haberdasher_pb2 import Size, Hat

class LoggingInterceptor:
    """Interceptor that logs all requests and responses"""

    async def intercept_unary(self, next, request, ctx):
        print(f"[LOG] Calling {ctx.method().name} with request: {request}")
        try:
            response = await next(request, ctx)
            print(f"[LOG] Received response: {response}")
            return response
        except Exception as e:
            print(f"[LOG] Error: {e}")
            raise

async def main():
    # Create client with interceptors
    client = HaberdasherClient(
        "http://localhost:3000",
        interceptors=[LoggingInterceptor()]
    )

    try:
        response = await client.make_hat(
            Size(inches=12)
        )
        print(response)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

Client interceptors support all RPC types (unary, client streaming, server streaming, and bidirectional streaming) and work with both async and sync clients.

### Message Size Limits

Connecpy allows you to limit incoming message sizes to protect against resource exhaustion. By default, there is no limit, but you can set one by passing `read_max_bytes` to the application constructor:

```python
from haberdasher_connecpy import HaberdasherASGIApplication, HaberdasherWSGIApplication

# Set maximum message size to 1MB for ASGI applications
app = HaberdasherASGIApplication(
    service,
    read_max_bytes=1024 * 1024  # 1MB
)

# Set maximum message size for WSGI applications
wsgi_app = HaberdasherWSGIApplication(
    service_sync,
    read_max_bytes=1024 * 1024  # 1MB
)

# Disable message size limit (not recommended for production)
app = HaberdasherASGIApplication(
    service,
    read_max_bytes=None
)
```

When a message exceeds the configured limit, the server will return a `RESOURCE_EXHAUSTED` error to the client.

## Standing on the shoulders of giants

The initial version (1.0.0) of this software was created by modifying https://github.com/verloop/twirpy at January 4, 2024, so that it supports Connect Protocol.
