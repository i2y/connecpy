import httpx

from . import exceptions
from . import errors


class ConnecpyClient:
    def __init__(self, address, timeout=5):
        self._address = address
        self._timeout = timeout

    def _make_request(self, *, url, request, ctx, response_obj, **kwargs):
        headers = ctx.get_headers()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers
        kwargs["headers"]["Content-Type"] = "application/proto"

        if "timeout" not in kwargs:
            kwargs["timeout"] = self._timeout
            kwargs["headers"]["connect-timeout-ms"] = str(self._timeout * 1000)

        try:
            with httpx.Client() as client:
                resp = client.post(
                    url=self._address + url,
                    content=request.SerializeToString(),
                    **kwargs,
                )
                resp.raise_for_status()

                if resp.status_code == 200:
                    response = response_obj()
                    response.ParseFromString(resp.content)
                    return response
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
        except Exception as e:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Internal,
                message=str(e),
            )
