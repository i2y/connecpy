from collections.abc import ItemsView, KeysView, Mapping, MutableMapping, ValuesView
from typing import Iterator, Optional, Sequence

__all__ = ["Headers"]


class Headers(MutableMapping[str, str]):
    """Container of HTTP headers.

    This class behaves like a dictionary with case-insensitive keys and
    string values. It additionally can be used to store multiple values for
    the same key by using the `add` method, and retrieve a view including
    duplicates using `allitems`.
    """

    _store: dict[str, str]
    _extra: Optional[dict[str, list[str]]]

    def __init__(
        self, items: Mapping[str, str] | Sequence[tuple[str, str]] = ()
    ) -> None:
        self._extra = None
        if isinstance(items, Mapping):
            self._store = {k.lower(): v for k, v in items.items()}
        else:
            self._store = {}
            for k, v in items:
                self.add(k, v)

    def __getitem__(self, key: str) -> str:
        key = key.lower()
        return self._store[key]

    def __setitem__(self, key: str, value: str) -> None:
        key = key.lower()
        self._store[key] = value
        if self._extra is not None:
            self._extra.pop(key, None)

    def __delitem__(self, key: str) -> None:
        key = key.lower()
        del self._store[key]
        # If value wasn't in store, it's not in extra
        # so no need to worry about exception.
        if self._extra is not None:
            self._extra.pop(key, None)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def add(self, key: str, value: str) -> None:
        """Add a header, appending to existing values without overwriting.

        To overwrite an existing value, use `self[key] = value` instead.
        """
        key = key.lower()
        if key in self._store:
            if self._extra is None:
                self._extra = {}
            self._extra.setdefault(key, []).append(value)
            return
        self._store[key] = value

    def clear(self) -> None:
        """Clear all headers."""
        self._store.clear()
        self._extra = None

    def getall(self, key: str) -> Sequence[str]:
        """Get all values for a header key, including duplicates."""
        key = key.lower()
        if key not in self._store:
            return ()
        res = [self._store[key]]
        if self._extra is not None:
            res.extend(self._extra.get(key, ()))
        return res

    def allitems(self) -> ItemsView[str, str]:
        """Return an iterable view of all header items, including duplicates."""
        if self._extra is None:
            return self._store.items()
        return _AllItemsView(self)

    # Commonly used functions that delegate to _store for performance vs the base class
    # implementations that rely on dunder methods.

    def items(self) -> ItemsView[str, str]:
        """Return an iterable view of the headers, without duplicates."""
        return self._store.items()

    def keys(self) -> KeysView[str]:
        """Return an iterable view of the header keys."""
        return self._store.keys()

    def values(self) -> ValuesView[str]:
        """Return an iterable view of the header values, without duplicates."""
        return self._store.values()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        key = key.lower()
        return key in self._store


class _AllItemsView(ItemsView[str, str]):
    """An iterable view of all header items, including duplicates."""

    def __init__(self, headers: Headers):
        self._headers = headers

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for key, value in self._headers._store.items():
            yield (key, value)
            if self._headers._extra:
                for value in self._headers._extra.get(key, ()):
                    yield (key, value)

    def __len__(self) -> int:
        size = len(self._headers._store)
        if self._headers._extra:
            size += sum(len(v) for v in self._headers._extra.values())
        return size
