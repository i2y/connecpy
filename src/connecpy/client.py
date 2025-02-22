import httpx

from . import exceptions
from . import errors
from . import compression
from . import shared_client


class ConnecpyClient:
    def __init__(self, address, timeout=5):
        self._address = address
        self._timeout = timeout

    def _make_request(
        self, *, url, request, ctx, response_obj, method="POST", **kwargs
    ):
        """Make an HTTP request to the server."""
        # Prepare headers and kwargs using shared logic
        headers, kwargs = shared_client.prepare_headers(ctx, kwargs, self._timeout)

        try:
            with httpx.Client() as client:
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
                    resp = client.get(url=self._address + url, **kwargs)
                else:
                    resp = client.post(
                        url=self._address + url, content=request_data, **kwargs
                    )

                resp.raise_for_status()

                if resp.status_code == 200:
                    response = response_obj()
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
