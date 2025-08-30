# connect-python

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/github/connect-python/actions/workflows/ci.yaml/badge.svg)](https://github.com/github/connect-python/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/github/connect-python/graph/badge.svg)](https://codecov.io/github/github/connect-python)
[![PyPI version](https://img.shields.io/pypi/v/connectrpc)](https://pypi.org/project/connectrpc)

A Python implementation of the [Connect RPC framework](https://connectrpc.com/).

This repo contains a protoc plugin that generates sever and client code and a pypi package with common implementation details.

## Features

- Client backed by [httpx](https://www.python-httpx.org/)
- WSGI and ASGI server implementations for use with any Python app server
- Fully type-annotated, including the generated code, and verified
  with pyright.
- Verified implementation using the official
  [conformance](https://github.com/connectprc/conformance) test
  suite.

## Usage

With a protobuf definition in hand, you can generate stub code. This is
easiest using buf, but you can also use protoc if you're feeling
masochistic.

Install the compiler (e.g. `pip install protoc-gen-connect-python`), and
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

`protoc-gen-connect-python` is only needed for code generation. Your actual
application should include `connect-python` as a dependency for the runtime
component.

For more usage details, see the [docs](./docs/usage.md).

### Server runtime dependencies

To run the server, you'll need one of the following: [Uvicorn](https://www.uvicorn.org/), [Daphne](https://github.com/django/daphne), or [Hypercorn](https://gitlab.com/pgjones/hypercorn). If your goal is to support both HTTP/1.1 and HTTP/2, you should opt for either Daphne or Hypercorn. Additionally, to test the server, you might need a client command, such as [buf](https://buf.build/docs/installation).

## Development

We use `ruff` for linting and formatting, and `pyright` for type checking.

We rely on the conformance test suit (in
[./conformance](./conformance)) to verify behavior.

Set up a virtual env:

```sh
uv sync
```

Then, use `uv run just check` to do development checks:

```console
$ uv run just --list
Available recipes:
    all                    # Run all checks (format, check, mypy, test, integration-test)
    check                  # Check code with ruff linter
    conformance-test *ARGS # Run conformance tests (requires connectconformance binary). Usage: uv run just conformance-test [ARGS...]
    fix                    # Fix auto-fixable ruff linter issues
    format                 # Format code with ruff
    integration-test       # Run integration test against demo.connectrpc.com
    mypy                   # Run mypy type checking
    mypy-package
    mypy-tests
    protoc-gen *ARGS       # Run protoc with connect_python plugin (development mode). usage: uv run just protoc-gen [PROTOC_ARGS...]
    test                   # Run tests
```

For example, `uv run just check` will lint code.

## Status

This project is in alpha and is being actively developed. Expect breaking changes.

## Legal

Offered under the [Apache 2 license](/LICENSE).
