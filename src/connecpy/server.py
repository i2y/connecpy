from . import exceptions
from . import errors


class ConnecpyServer:
    """
    Represents a Connecpy server that handles incoming requests and dispatches them to the appropriate endpoints.
    """

    def __init__(self):
        self._endpoints = {}
        self._prefix = ""

    @property
    def prefix(self):
        """
        Represents the prefix used for routing requests to endpoints.
        """
        return self._prefix

    def get_endpoint(self, path):
        """
        Get the endpoint associated with the given path.

        Args:
            path (str): The path of the request.

        Returns:
            object: The endpoint associated with the given path.

        Raises:
            ConnecpyServerException: If no handler is found for the path or if the service has no endpoint for the given method.
        """
        (_, url_pre, rpc_method) = path.rpartition(f"{self._prefix}/")

        if not url_pre or not rpc_method:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.BadRoute,
                message=f"no handler for path {path}",
            )

        endpoint = self._endpoints.get(rpc_method, None)
        if not endpoint:
            raise exceptions.ConnecpyServerException(
                code=errors.Errors.Unimplemented,
                message=f"service has no endpoint {rpc_method}",
            )

        return endpoint
