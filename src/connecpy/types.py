from typing import Mapping, Sequence

import httpx

# Redefined from httpx since not exported
type Headers = (
    httpx.Headers
    | Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[tuple[str, str]]
    | Sequence[tuple[bytes, bytes]]
)
