"""Identity-based, document-owned strong references."""

from uuid import uuid4


class APIError(ValueError):
    """A safe error suitable for clients."""


class ObjectRegistry:
    def __init__(self) -> None:
        self._objects: dict[str, object] = {}
        self._identities: dict[int, str] = {}

    def register(self, obj: object) -> str:
        identity = id(obj)
        if identity not in self._identities:
            handle = f"obj-{uuid4().hex}"
            self._identities[identity] = handle
            self._objects[handle] = obj
        return self._identities[identity]

    def get(self, handle: str) -> object:
        try:
            return self._objects[handle]
        except KeyError:
            raise APIError("unknown_object: Object does not belong to this document") from None
