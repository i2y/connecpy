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
