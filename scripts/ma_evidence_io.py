"""Shared integrity helpers for the historical M&A evidence scripts.

Paths are confined to an explicit root after symlink resolution; every source is
read once and its digest and parse come from those same bytes; review clocks are
measured, timezone-aware and never earlier than the evidence they review.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def confined(root: Path, reference: str | Path) -> Path:
    """Resolve a relative (or root-internal absolute) reference strictly inside root."""
    require(isinstance(reference, (str, Path)) and str(reference) != '', 'empty source path')
    base = Path(root).resolve(strict=True)
    candidate = Path(reference)
    if candidate.is_absolute():
        require(candidate.resolve(strict=False).is_relative_to(base), f'absolute path outside root {base}: {reference}')
    else:
        require('..' not in candidate.parts, f'path traversal rejected: {reference}')
        candidate = base / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f'missing source under {base}: {reference}') from exc
    require(resolved.is_relative_to(base), f'path escapes root {base} (symlink or traversal): {reference}')
    require(resolved.is_file(), f'not a regular file: {reference}')
    return resolved


def read_once(path: Path, expected_sha256: str | None = None, expected_bytes: int | None = None) -> tuple[bytes, str]:
    payload = Path(path).read_bytes()
    digest = sha256(payload)
    require(expected_sha256 is None or digest == expected_sha256, f'hash mismatch for {path}: {digest}')
    require(expected_bytes is None or len(payload) == expected_bytes, f'byte length mismatch for {path}')
    return payload, digest


def read_json_once(path: Path, expected_sha256: str | None = None) -> tuple[dict, bytes, str]:
    payload, digest = read_once(path, expected_sha256)
    return json.loads(payload), payload, digest


def measured_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_clock(value: str, field: str) -> datetime:
    require(isinstance(value, str), f'{field}: timestamp string required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f'{field}: timezone-aware timestamp required')
    return parsed


def review_clock(value: str, *, not_before: dict[str, str], now: datetime | None = None) -> str:
    """Validate an actual review time: aware, not future, and after every represented source clock."""
    reviewed = parse_clock(value, 'reviewed_at')
    current = now or measured_now()
    require(reviewed <= current, f'reviewed_at {value} is in the future of measured now {current.isoformat()}')
    for name, clock in not_before.items():
        require(parse_clock(clock, name) <= reviewed, f'reviewed_at {value} precedes source clock {name}={clock}')
    return reviewed.astimezone(timezone.utc).isoformat()


def chronology(label: str, start: str, ends: dict[str, str], *, now: datetime | None = None) -> None:
    """Require aware clocks with start <= every end <= measured now; never repairs a receipt."""
    current = now or measured_now()
    begun = parse_clock(start, f'{label}.start')
    require(begun <= current, f'{label}: start {start} is in the future of measured now {current.isoformat()}')
    for name, value in ends.items():
        ended = parse_clock(value, f'{label}.{name}')
        require(begun <= ended, f'{label}: {name} {value} precedes start {start}')
        require(ended <= current, f'{label}: {name} {value} is in the future of measured now {current.isoformat()}')
