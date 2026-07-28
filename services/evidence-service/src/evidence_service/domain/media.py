"""Content validation based on allowlisted MIME, extension and magic bytes."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from evidence_service.domain.errors import EvidenceError
from evidence_service.domain.models import MediaKind

IMAGE_LIMIT = 10 * 1024 * 1024
VIDEO_LIMIT = 250 * 1024 * 1024

_EXTENSIONS = {
    "image/jpeg": frozenset({"jpg", "jpeg"}),
    "image/png": frozenset({"png"}),
    "image/webp": frozenset({"webp"}),
    "video/mp4": frozenset({"mp4"}),
}


@dataclass(frozen=True, slots=True)
class MediaProbe:
    content_type: str
    media_kind: MediaKind
    width: int | None
    height: int | None


def _jpeg_dimensions(header: bytes) -> tuple[int, int] | None:
    cursor = 2
    while cursor + 9 <= len(header):
        if header[cursor] != 0xFF:
            cursor += 1
            continue
        marker = header[cursor + 1]
        cursor += 2
        if marker in {0xD8, 0xD9}:
            continue
        if cursor + 2 > len(header):
            return None
        length = int.from_bytes(header[cursor : cursor + 2], "big")
        if length < 2 or cursor + length > len(header):
            return None
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            height = int.from_bytes(header[cursor + 3 : cursor + 5], "big")
            width = int.from_bytes(header[cursor + 5 : cursor + 7], "big")
            return width, height
        cursor += length
    return None


def _webp_dimensions(header: bytes) -> tuple[int, int] | None:
    chunk = header[12:16]
    if chunk == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height
    if chunk == b"VP8 " and len(header) >= 30 and header[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", header[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L" and len(header) >= 25 and header[20] == 0x2F:
        packed = int.from_bytes(header[21:25], "little")
        return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
    return None


def probe_header(header: bytes) -> MediaProbe:
    if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
        width, height = struct.unpack(">II", header[16:24])
        return MediaProbe("image/png", MediaKind.IMAGE, width, height)
    if header.startswith(b"\xff\xd8\xff"):
        dimensions = _jpeg_dimensions(header)
        if dimensions is None:
            raise EvidenceError("EVIDENCE_MEDIA_INVALID")
        return MediaProbe("image/jpeg", MediaKind.IMAGE, *dimensions)
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        dimensions = _webp_dimensions(header)
        if dimensions is None:
            raise EvidenceError("EVIDENCE_MEDIA_INVALID")
        return MediaProbe("image/webp", MediaKind.IMAGE, *dimensions)
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V "}:
            return MediaProbe("video/mp4", MediaKind.VIDEO, None, None)
    raise EvidenceError("EVIDENCE_MEDIA_INVALID")


def validate_media(
    *,
    header: bytes,
    declared_content_type: str,
    extension: str,
    size_bytes: int,
    expected_kind: MediaKind,
    trusted_width: int | None,
    trusted_height: int | None,
    trusted_duration_ms: int | None,
) -> MediaProbe:
    extension = extension.casefold().lstrip(".")
    probe = probe_header(header)
    if (
        probe.content_type != declared_content_type
        or probe.media_kind is not expected_kind
        or extension not in _EXTENSIONS.get(declared_content_type, frozenset())
    ):
        raise EvidenceError("EVIDENCE_MEDIA_INVALID")
    limit = IMAGE_LIMIT if expected_kind is MediaKind.IMAGE else VIDEO_LIMIT
    if not 1 <= size_bytes <= limit:
        raise EvidenceError("EVIDENCE_MEDIA_TOO_LARGE")
    if expected_kind is MediaKind.IMAGE:
        if (
            trusted_duration_ms is not None
            or trusted_width != probe.width
            or trusted_height != probe.height
        ):
            raise EvidenceError("EVIDENCE_MEDIA_INVALID")
    elif (
        trusted_width is None
        or trusted_height is None
        or trusted_duration_ms is None
        or trusted_width < 1
        or trusted_height < 1
        or trusted_duration_ms < 1
    ):
        raise EvidenceError("EVIDENCE_MEDIA_INVALID")
    return probe
