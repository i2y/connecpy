import gzip
from collections.abc import KeysView
from typing import Optional, Protocol


class Compression(Protocol):
    def compress(self, data: bytes) -> bytes:
        """Compress the given data."""
        ...

    def decompress(self, data: bytes) -> bytes:
        """Decompress the given data."""
        ...


_compressions: dict[str, Compression] = {}


class GZipCompression(Compression):
    def compress(self, data: bytes) -> bytes:
        return gzip.compress(data)

    def decompress(self, data: bytes) -> bytes:
        return gzip.decompress(data)


_compressions["gzip"] = GZipCompression()

try:
    import brotli

    class BrotliCompression(Compression):
        def compress(self, data: bytes) -> bytes:
            return brotli.compress(data)

        def decompress(self, data: bytes) -> bytes:
            return brotli.decompress(data)

    _compressions["br"] = BrotliCompression()
except ImportError:
    pass

try:
    import zstandard

    class ZstdCompression(Compression):
        def compress(self, data: bytes) -> bytes:
            return zstandard.ZstdCompressor().compress(data)

        def decompress(self, data: bytes) -> bytes:
            # Support clients sending frames without length by using
            # stream API.
            with zstandard.ZstdDecompressor().stream_reader(data) as reader:
                return reader.read()

    _compressions["zstd"] = ZstdCompression()
except ImportError:
    pass


class IdentityCompression(Compression):
    def compress(self, data: bytes) -> bytes:
        """Return data as-is without compression."""
        return data

    def decompress(self, data: bytes) -> bytes:
        """Return data as-is without decompression."""
        return data


_compressions["identity"] = IdentityCompression()


def get_compression(name: str) -> Optional[Compression]:
    return _compressions.get(name.lower())


def get_available_compressions() -> KeysView:
    """Returns a list of available compression names."""
    return _compressions.keys()


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
            candidates = [enc for enc in _compressions if enc not in excluded]
            if candidates:
                return candidates[0]
            else:
                # If all available encodings were explicitly mentioned, return the first available.
                return next(iter(get_available_compressions()))
        elif client_encoding in _compressions:
            return client_encoding

    # If no match found, fallback to identity
    return "identity"
