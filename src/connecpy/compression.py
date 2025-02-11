from collections.abc import Callable
import gzip
import brotli
import zstandard



def gzip_decompress(data: bytes) -> bytes:
    """Decompress data using gzip."""
    try:
        return gzip.decompress(data)
    except gzip.BadGzipFile:
        raise


def brotli_decompress(data: bytes) -> bytes:
    """Decompress data using brotli."""
    try:
        return brotli.decompress(data)
    except brotli.error:
        raise


def zstd_decompress(data: bytes) -> bytes:
    """Decompress data using zstandard."""
    try:
        dctx = zstandard.ZstdDecompressor()
        return dctx.decompress(data)
    except zstandard.ZstdError:
        raise


def gzip_compress(data: bytes) -> bytes:
    """Compress data using gzip."""
    try:
        return gzip.compress(data)
    except Exception:
        raise


def brotli_compress(data: bytes) -> bytes:
    """Compress data using brotli."""
    try:
        return brotli.compress(data)
    except Exception:
        raise


def zstd_compress(data: bytes) -> bytes:
    """Compress data using zstandard."""
    try:
        cctx = zstandard.ZstdCompressor()
        return cctx.compress(data)
    except Exception:
        raise


def identity(data: bytes) -> bytes:
    """Return data as-is without compression."""
    return data


_decompressors = {
    "identity": identity,
    "gzip": gzip_decompress,
    "br": brotli_decompress,
    "zstd": zstd_decompress,
}


def get_decompressor(compression_name: str) -> Callable[[bytes], bytes] | None:
    """Get decompressor function by compression name.

    Args:
        compression_name (str): The name of the compression. Can be "identity", "gzip", "br", or "zstd".

    Returns:
        Callable[[bytes], bytes]: The decompressor function for the specified compression.
    """
    cmp_lower = compression_name.lower()
    decompressor = _decompressors.get(cmp_lower)
    if decompressor:
        return decompressor

    return None


def get_compressor(compression_name: str) -> Callable[[bytes], bytes]:
    """Get compressor function by compression name.

    Args:
        compression_name (str): The name of the compression. Can be "identity", "gzip", "br", or "zstd".

    Returns:
        Callable[[bytes], bytes]: The compressor function for the specified compression.
    """
    compressors = {
        "identity": identity,
        "gzip": gzip_compress,
        "br": brotli_compress,
        "zstd": zstd_compress,
    }
    return compressors.get(compression_name)


def extract_header_value(
    headers: list[tuple[bytes, bytes]] | dict[str, str], name: bytes | str
) -> bytes | str:
    """Get a header value from a list of headers or a headers dictionary.

    Args:
        headers: Either a list of (name, value) tuples with bytes, or a dictionary with string keys/values
        name: Header name to look for (either bytes or str)

    Returns:
        The header value if found, empty bytes or string depending on input type
    """
    if isinstance(headers, dict):
        # Dictionary case - string keys
        name = name.decode("ascii") if isinstance(name, bytes) else name
        name = name.lower()
        return headers.get(name, "")
    else:
        # List of tuples case - bytes
        name = name.encode("ascii") if isinstance(name, str) else name
        name_lower = name.lower()
        for key, value in headers:
            if key.lower() == name_lower:
                return value
        return b""


def parse_accept_encoding(accept_encoding: str | bytes) -> list[tuple[str, float]]:
    """Parse Accept-Encoding header value with quality values.

    Args:
        accept_encoding: The Accept-Encoding header value (str or bytes)

    Returns:
        list[tuple[str, float]]: List of (encoding, q-value) pairs, sorted by q-value
    """
    if not accept_encoding:
        return [("identity", 1.0)]

    # Convert bytes to string if needed
    if isinstance(accept_encoding, bytes):
        accept_encoding = accept_encoding.decode("ascii")

    encodings = []
    seen = set()  # Track seen encodings to avoid duplicates

    # First, handle special case of "identity;q=0,*;q=0" which means "no encoding allowed"
    if accept_encoding.replace(" ", "") == "identity;q=0,*;q=0":
        return [("identity", 0.0), ("*", 0.0)]

    for part in accept_encoding.split(","):
        part = part.strip()
        if not part:
            continue

        # Split encoding and q-value
        if ";" in part:
            encoding, q_part = part.split(";", 1)
            encoding = encoding.strip().lower()
            try:
                if not q_part.strip().lower().startswith("q="):
                    continue
                q = float(q_part.strip().lower().replace("q=", ""))
                q = max(0.0, min(1.0, q))  # Clamp between 0 and 1
            except (ValueError, AttributeError):
                q = 1.0
        else:
            encoding = part.strip().lower()
            q = 1.0

        if encoding and encoding not in seen:
            seen.add(encoding)
            encodings.append((encoding, q))

    # Sort by q-value in descending order while preserving the original accept-encoding order for equal q-values
    result = sorted(encodings, key=lambda x: -x[1])
    return result


# TODO: wrong sorting order, use preference order instead of available order
def select_encoding(
    accept_encoding: str | bytes,
    available_encodings: tuple[str] = ("br", "gzip", "zstd", "identity"),
) -> str:
    """Select the best compression encoding based on Accept-Encoding header.

    Args:
        accept_encoding: The Accept-Encoding header value (str or bytes)
        available_encodings: Tuple of available encodings.
            Defaults to ("br", "gzip", "zstd", "identity")

    Returns:
        str: The selected encoding name
    """
    # Parse Accept-Encoding header with q-values (already sorted by q descending)
    encodings = parse_accept_encoding(accept_encoding)

    # Check for "no encoding allowed" case
    if len(encodings) == 2 and all(q == 0.0 for _, q in encodings):
        if {"identity", "*"} == {enc for enc, _ in encodings}:
            return "identity"

    # Iterate over client-preferred encodings (sorted by q-value)
    for client_encoding, q in encodings:
        if q <= 0:
            continue
        if client_encoding == "*":
            # For wildcard, choose any available encoding not explicitly defined by the client.
            excluded = {enc for enc, _ in encodings if enc != "*"}
            candidates = [enc for enc in available_encodings if enc not in excluded]
            if candidates:
                return candidates[0]
            else:
                # If all available encodings were explicitly mentioned, return the first available.
                return available_encodings[0]
        elif client_encoding in available_encodings:
            return client_encoding

    # If no match found, fallback to identity
    return "identity"
