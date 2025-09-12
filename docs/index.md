# connect-python

A Python implementation of the Connect RPC framework.

This provides a client and server runtime for both synchronous and
asynchronous Python applications, as well as a stub code generator,
to let Python programs use the Connect protocol.

## Features

- Client backed by [httpx](https://www.python-httpx.org/)
- WSGI and ASGI server implementations for use with any Python app server
- Fully type-annotated, including the generated code, and verified
  with pyright.
- Verified implementation using the official
  [conformance](https://github.com/connectprc/conformance) test
  suite.

## Installation

For basic client functionality:

```bash
uv add connect-python
# Or pip install connect-python
```

For code generation, you will need the protoc plugin. This should generally
only be needed as a dev dependency.

```bash
uv add --dev protoc-gen-connect-python
# Or pip install protoc-gen-connect-python
```

## Quick Start

With a protobuf definition in hand, you can generate stub code. This is
easiest using buf, but you can also use protoc if you're feeling
masochistic.

Install the compiler (eg `pip install protoc-gen-connect-python`), and
it can be referenced as `protoc-gen-connect-python`.

A reasonable `buf.gen.yaml`:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: .
  - remote: buf.build/protocolbuffers/pyi
    out: .
  - local: .venv/bin/protoc-gen-connect-python
    out: .
```
