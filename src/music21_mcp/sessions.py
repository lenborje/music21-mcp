"""Document lifetime and explicit local MusicXML import."""

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile, is_zipfile

from music21 import converter, stream

from .registry import APIError, ObjectRegistry


@dataclass
class Document:
    root: stream.Stream
    name: str
    id: str = field(default_factory=lambda: f"doc-{uuid4().hex}")
    registry: ObjectRegistry = field(default_factory=ObjectRegistry)

    def summary(self) -> dict[str, str]:
        return {
            "document_id": self.id,
            "name": self.name,
            "root": self.registry.register(self.root),
        }


class SessionManager:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def get(self, document_id: str) -> Document:
        try:
            return self._documents[document_id]
        except KeyError:
            raise APIError("unknown_document: Document is not open") from None

    def open(self, path: str) -> dict[str, str]:
        source = Path(path).expanduser()
        try:
            if source.suffix.lower() not in {".xml", ".musicxml", ".mxl"}:
                raise APIError("invalid_file: Expected a local MusicXML file")
            if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
                raise APIError("invalid_file: Missing file or file exceeds 20 MiB")
            if is_zipfile(source):
                with ZipFile(source) as archive:
                    if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                        raise APIError("invalid_file: Expanded MXL exceeds 100 MiB")
            root = converter.parse(source.resolve(), format="musicxml", forceSource=True)
        except APIError:
            raise
        except (OSError, BadZipFile):
            raise APIError("invalid_file: Cannot read MusicXML file") from None
        except Exception:
            raise APIError("parse_error: Cannot parse MusicXML file") from None
        if not isinstance(root, stream.Stream):
            raise APIError("parse_error: Expected a MusicXML score")
        document = Document(root, source.name)
        self._documents[document.id] = document
        return document.summary()

    def list(self) -> list[dict[str, str]]:
        return [doc.summary() for doc in self._documents.values()]

    def close(self, document_id: str) -> dict[str, bool]:
        self.get(document_id)
        del self._documents[document_id]
        return {"closed": True}
