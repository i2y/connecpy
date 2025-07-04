from enum import Enum


class Errors(Enum):
    """
    Enum class representing different error codes and their corresponding status codes.
    """

    Canceled = "canceled"
    Unknown = "unknown"
    InvalidArgument = "invalid_argument"
    DeadlineExceeded = "deadline_exceeded"
    NotFound = "not_found"
    AlreadyExists = "already_exists"
    PermissionDenied = "permission_denied"
    ResourceExhausted = "resource_exhausted"
    FailedPrecondition = "failed_precondition"
    Aborted = "aborted"
    OutOfRange = "out_of_range"
    Unimplemented = "unimplemented"
    Internal = "internal"
    Unavailable = "unavailable"
    DataLoss = "data_loss"
    Unauthenticated = "unauthenticated"

    @staticmethod
    def from_string(code: str) -> "Errors":
        """
        Converts a string code to an Errors enum member.

        Args:
            code (str): The error code as a string.

        Returns:
            Errors: The corresponding Errors enum member.
        """
        try:
            return Errors(code)
        except ValueError:
            return Errors.Unknown

    @staticmethod
    def get_status_code(code: "Errors") -> int:
        """
        Returns the corresponding HTTP status code for the given error code.

        Args:
            code (Errors): The error code.

        Returns:
            int: The corresponding HTTP status code.
        """
        return {
            Errors.Canceled: 408,
            Errors.Unknown: 500,
            Errors.InvalidArgument: 400,
            Errors.DeadlineExceeded: 408,
            Errors.NotFound: 404,
            Errors.AlreadyExists: 409,
            Errors.PermissionDenied: 403,
            Errors.Unauthenticated: 401,
            Errors.ResourceExhausted: 429,
            Errors.FailedPrecondition: 412,
            Errors.Aborted: 409,
            Errors.OutOfRange: 400,
            Errors.Unimplemented: 501,
            Errors.Internal: 500,
            Errors.Unavailable: 503,
            Errors.DataLoss: 500,
        }.get(code, 500)
