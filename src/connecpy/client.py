from typing import Optional

import httpx

from google.protobuf.message import Message

from . import context
from . import exceptions
from . import errors
from . import compression
from . import shared_client


class ConnecpyClient:
    """
    Represents a synchronous client for Connecpy using httpx.

    Args:
        address (str): The address of the Connecpy server.
        session (httpx.Client): The httpx client session to use for making requests.
    """

    def __init__(self, address: str, timeout=5, session: Optional[httpx.Client] = None):
        self._address = address
        self._timeout = timeout
        if session:
            self._session = session
            self._close_client = False
        else:
            self._session = httpx.Client()
            self._close_client = True
        self._closed = False

    def close(self):
        """Close the HTTP client. After closing, the client cannot be used to make requests."""
        if not self._closed:
            self._closed = True
            if self._close_client:
                self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()

    def _make_request(
        self,
        *,
        url,
        request: Message,
        ctx: Optional[context.ClientContext],
        response_class: type[Message],
        method="POST",
        **kwargs,
    ):
        """Make an HTTP request to the server."""
        # Prepare headers and kwargs using shared logic
        headers, kwargs = shared_client.prepare_headers(ctx, kwargs, self._timeout)

        try:
            if "content-encoding" in headers:
                request_data, headers = shared_client.compress_request(
                    request, headers, compression
                )
            else:
                request_data = request.SerializeToString()

            if method == "GET":
                params = shared_client.prepare_get_params(request_data, headers)
                kwargs["params"] = params
                kwargs["headers"].pop("content-type", None)
                resp = self._session.get(url=self._address + url, **kwargs)
            else:
                resp = self._session.post(
                    url=self._address + url, content=request_data, **kwargs
                )

            resp.raise_for_status()

            if resp.status_code == 200:
                response = response_class()
                try:
                    response.ParseFromString(resp.content)
                    return response
                except Exception as e:
                    raise exceptions.ConnecpyException(
                        f"Failed to parse response message: {str(e)}"
                    )
            else:
                raise exceptions.ConnecpyServerException.from_json(resp.json())

        except httpx.TimeoutException as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.DeadlineExceeded,
                message=str(e) or "request timeout",
            )
        except httpx.HTTPStatusError as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unavailable,
                message=str(e),
            )
        except exceptions.ConnecpyException:
            raise
        except Exception as e:
            raise exceptions.ConnecpyException(str(e))
