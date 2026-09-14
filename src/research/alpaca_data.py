"""Read-only Alpaca stock data with replayable source receipts.

Historical symbol mapping is explicit. Neither current vendor data nor an empty
bar result establishes an original data vintage, listing status or M&A outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import shlex
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = 'https://data.alpaca.markets/v2/stocks/bars'
PAGE_LIMIT = 10000
MAX_BYTES = 20_000_000
CREDENTIAL_PAIRS = (('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY'),
                    ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'timezone-aware market-data timestamp required')
    return parsed.astimezone(timezone.utc)


def canonical(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def immutable_json(value: dict, directory: Path, prefix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    path = directory / f'{prefix}-{digest(raw)}.json'
    if path.exists():
        require(path.read_bytes() == raw, 'immutable market artifact changed')
    else:
        with path.open('xb') as handle:
            handle.write(raw)
    return path


@dataclass(frozen=True)
class Credentials:
    key_id: str = field(repr=False)
    secret_key: str = field(repr=False)

    def __post_init__(self):
        require(all(isinstance(value, str) and bool(value) and
                    all(33 <= ord(char) <= 126 for char in value)
                    for value in (self.key_id, self.secret_key)),
                'invalid Alpaca credential header configuration')


class AlpacaAccessError(ValueError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def credential_source(env_file: Path | None = None) -> Path | None:
    """Resolve one configuration source; never fall back after an invalid pair.

    None denotes the process environment. Shared credentials remain outside the
    repository; neither their values nor their scoped paper/live pairs are copied.
    """
    if env_file is not None:
        return Path(env_file).expanduser()
    if any(os.environ.get(key) for pair in CREDENTIAL_PAIRS for key in pair):
        return None
    reference = os.environ.get('ALPACA_CREDENTIALS_FILE')
    if reference:
        return Path(reference).expanduser()
    shared = Path.home() / '.config/alpaca_creds.env'
    return shared if shared.is_file() else None


def load_credentials(env_file: Path | None = None) -> Credentials:
    """Read only known key names; never execute a dotenv file or log its values."""
    env_file = credential_source(env_file)
    known = {key for pair in CREDENTIAL_PAIRS for key in pair}
    values = {}
    if env_file is not None:
        for line in env_file.read_text().splitlines():
            key, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and key.strip() in known:
                parts = shlex.split(value, comments=True)
                require(len(parts) <= 1, 'invalid Alpaca credential configuration')
                require(key.strip() not in values, 'duplicate Alpaca credential variable')
                values[key.strip()] = parts[0] if parts else ''
    else:
        values = {key: os.environ.get(key, '') for key in known}
    pairs = []
    for key, secret in CREDENTIAL_PAIRS:
        if values.get(key) or values.get(secret):
            require(bool(values.get(key)) and bool(values.get(secret)), 'incomplete Alpaca credential pair')
            pairs.append((values[key], values[secret]))
    if not pairs:
        raise AlpacaAccessError('Alpaca credentials are not configured; supply an environment or --env-file')
    require(len(set(pairs)) == 1, 'conflicting Alpaca credential pairs; choose one configuration')
    for value in pairs[0]:
        require(not any(c.isspace() for c in value) and '$' not in value and
                not value.lower().startswith(('your_', 'replace', 'example', '<')),
                'Alpaca credential is a placeholder or unresolved reference')
    return Credentials(*pairs[0])


def make_request(symbols: list[str], start: str, end: str, asof: str, feed: str = 'sip') -> dict:
    require(isinstance(symbols, list) and 0 < len(symbols) <= 100 and
            all(isinstance(s, str) and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}', s) for s in symbols),
            'one to 100 explicit historical stock symbols required')
    require(len(set(symbols)) == len(symbols), 'duplicate requested stock symbol')
    require(timestamp(start) <= timestamp(end) <= datetime.now(timezone.utc), 'invalid or future bar interval')
    require(date.fromisoformat(asof).isoformat() == asof and asof == timestamp(end).date().isoformat(),
            'symbol asof must be the historical request-end date')
    require(feed in {'sip', 'iex'}, 'explicit SIP or IEX feed required; feeds cannot be substituted')
    return {'symbols': sorted(symbols), 'start': timestamp(start).isoformat(), 'end': timestamp(end).isoformat(),
            'asof': asof, 'feed': feed, 'adjustment': 'raw', 'timeframe': '1Day', 'currency': 'USD'}


def request_url(request: dict, page_token: str | None = None) -> str:
    expected = make_request(request['symbols'], request['start'], request['end'], request['asof'], request['feed'])
    require(request == expected, 'market request differs from raw daily USD contract')
    query = dict(expected, symbols=','.join(expected['symbols']), limit=PAGE_LIMIT, sort='asc')
    if page_token is not None:
        require(isinstance(page_token, str) and bool(page_token) and len(page_token) <= 4096,
                'invalid Alpaca pagination token')
        query['page_token'] = page_token
    return ENDPOINT + '?' + urlencode(query)


def parse_page(raw: bytes, request: dict) -> tuple[dict, str | None]:
    response = json.loads(raw)
    require(isinstance(response, dict) and 'bars' in response and 'next_page_token' in response,
            'incomplete Alpaca bars response')
    bars = response['bars'] if response['bars'] is not None else {}
    require(isinstance(bars, dict) and set(bars) <= set(request['symbols']), 'unexpected symbol in Alpaca response')
    count = 0
    for symbol, rows in bars.items():
        require(isinstance(rows, list), 'invalid Alpaca bar series')
        previous = None
        for row in rows:
            require(isinstance(row, dict), 'invalid Alpaca bar')
            at = timestamp(row['t'])
            require(timestamp(request['start']) <= at <= timestamp(request['end']), 'bar outside requested interval')
            require(previous is None or previous < at, 'duplicate or unsorted stock bars')
            previous = at
            for key in ('o', 'h', 'l', 'c', 'v'):
                value = row[key]
                require(type(value) in (int, float) and math.isfinite(value), 'nonfinite or missing OHLCV value')
            require(row['v'] >= 0 and 0 < row['l'] <= min(row['o'], row['c']) <=
                    max(row['o'], row['c']) <= row['h'], 'invalid OHLCV bounds')
            for key in ('n', 'vw'):
                if row.get(key) is not None:
                    require(type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] >= 0,
                            'invalid optional Alpaca bar value')
            count += 1
    require(count <= PAGE_LIMIT, 'Alpaca response exceeds page limit')
    token = response['next_page_token']
    require(token is None or (isinstance(token, str) and bool(token) and len(token) <= 4096),
            'invalid next-page token')
    return bars, token


def confined_bytes(directory: Path, relative: str) -> bytes:
    part = Path(relative)
    path = (directory / part).resolve()
    require(not part.is_absolute() and path.is_relative_to(directory.resolve()), 'market source path escapes evidence directory')
    return path.read_bytes()


def verify_bars_manifest(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    require(value.get('schema_version') == 'alpaca-stock-bars-v1', 'unsupported Alpaca bars manifest')
    request = value['request']
    request_url(request)
    pages = value['pages']
    require(isinstance(pages, list) and bool(pages), 'Alpaca response pages missing')
    combined = {s: [] for s in request['symbols']}
    token, used, retrieved = None, set(), []
    last_order = None
    for index, page in enumerate(pages):
        url = request_url(request, token)
        require(page['source_uri'] == page['effective_source_uri'] == url, 'Alpaca page query identity changed')
        raw = confined_bytes(path.parent, page['source_relative_path'])
        require(digest(raw) == page['source_sha256'] and len(raw) == page['source_bytes'], 'Alpaca source hash/size mismatch')
        at = timestamp(page['retrieved_at'])
        require(timestamp(request['end']) <= at <= datetime.now(timezone.utc), 'market source retrieval chronology invalid')
        require(not retrieved or retrieved[-1] <= at, 'market response page retrieval clocks are reversed')
        rows, following = parse_page(raw, request)
        for symbol in sorted(rows):
            for row in rows[symbol]:
                order = (symbol, timestamp(row['t']))
                require(last_order is None or last_order < order, 'Alpaca pagination overlaps or is out of order')
                last_order = order
                combined[symbol].append(row)
        if following is not None:
            require(following not in used and index < len(pages) - 1, 'Alpaca pagination cycle or missing final page')
            used.add(following)
        else:
            require(index == len(pages) - 1, 'extra page after completed Alpaca query')
        token = following
        retrieved.append(at)
    require(token is None and combined == value['bars_by_symbol'], 'Alpaca query incomplete or normalized bars changed')
    require(value.get('query_complete') is True and value.get('original_vendor_vintage_archived') is False
            and value.get('outcome_label') is None, 'market data cannot assert original vintage or an acquisition outcome')
    require(timestamp(value['retrieved_at']) == max(retrieved), 'market manifest retrieval differs from source pages')
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _fetch(url: str, credentials: Credentials) -> tuple[bytes, dict]:
    require(url.startswith(ENDPOINT + '?'), 'only the fixed Alpaca stock-data endpoint is permitted')
    require(isinstance(credentials, Credentials), 'explicit validated Alpaca credentials required')
    credentials.__post_init__()
    try:
        request = Request(url, headers={'APCA-API-KEY-ID': credentials.key_id,
                                       'APCA-API-SECRET-KEY': credentials.secret_key,
                                       'Accept': 'application/json',
                                       'User-Agent': 'biotech-ma-predictor local read-only market research'})
        with build_opener(_NoRedirect()).open(request, timeout=25) as response:
            require(response.status == 200 and response.geturl() == url, 'Alpaca response endpoint changed')
            raw = response.read(MAX_BYTES + 1)
            require(len(raw) <= MAX_BYTES, 'Alpaca response exceeds bounded size')
            return raw, {'effective_source_uri': response.geturl(),
                         'retrieved_at': datetime.now(timezone.utc).isoformat()}
    except HTTPError as exc:
        # Do not print authentication headers or arbitrary server response bodies.
        raise AlpacaAccessError(f'Alpaca market-data request rejected (HTTP {exc.code}); no automatic retry or feed fallback', exc.code) from None
    except (OSError, HTTPException, ValueError) as exc:
        # HTTP parsers and header setup can include arbitrary header values in
        # exception messages. Retain only the exception class, never its text.
        raise AlpacaAccessError(f'Alpaca market-data transport failed ({type(exc).__name__}); no automatic retry') from None


def collect_bars(symbols: list[str], start: str, end: str, asof: str, output_dir: Path, *,
                 feed: str = 'sip', credentials: Credentials | None = None, refresh: bool = False) -> Path:
    request = make_request(symbols, start, end, asof, feed)
    key = digest(canonical(request))
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = output_dir / f'query-{key}.json'
    failure = output_dir / f'failure-{key}.json'
    if cache.exists() and not refresh:
        reference = json.loads(cache.read_bytes())
        raw = confined_bytes(output_dir, reference['manifest_relative_path'])
        require(digest(raw) == reference['manifest_sha256'], 'cached Alpaca manifest hash mismatch')
        path = output_dir / reference['manifest_relative_path']
        require(verify_bars_manifest(path)['request'] == request, 'cached Alpaca request identity mismatch')
        return path
    if failure.exists():
        recorded = json.loads(failure.read_bytes())
        raise AlpacaAccessError('prior Alpaca request failed; resolve configuration/source access before a new collection directory', recorded.get('http_status'))
    credentials = credentials or load_credentials()
    pages, combined, token, tokens = [], {s: [] for s in request['symbols']}, None, set()
    try:
        for _ in range(100):
            url = request_url(request, token)
            if pages:
                time.sleep(0.35)
            raw, receipt = _fetch(url, credentials)
            relative = f'raw/{digest(raw)}.json'
            (output_dir / 'raw').mkdir(exist_ok=True)
            raw_path = output_dir / relative
            if raw_path.exists():
                require(raw_path.read_bytes() == raw, 'immutable Alpaca source changed')
            else:
                raw_path.write_bytes(raw)
            pages.append(dict(receipt, source_uri=url, source_relative_path=relative,
                              source_sha256=digest(raw), source_bytes=len(raw)))
            rows, following = parse_page(raw, request)
            for symbol, entries in rows.items():
                combined[symbol].extend(entries)
            if following is None:
                break
            require(following not in tokens, 'Alpaca pagination token repeated')
            tokens.add(following)
            token = following
        else:
            raise ValueError('Alpaca collection page bound exceeded')
        manifest = {'schema_version': 'alpaca-stock-bars-v1', 'request': request, 'pages': pages,
                    'bars_by_symbol': combined, 'query_complete': True, 'outcome_label': None,
                    'original_vendor_vintage_archived': False, 'retrieved_at': pages[-1]['retrieved_at'],
                    'limitations': ['Current vendor reconstruction of historical daily bars; not an original-vintage archive.',
                                    'Historical asof maps symbols; no CIK or historical membership is proved by bars.',
                                    'Raw OHLCV is not corporate-action-adjusted; no missing symbol implies an outcome.']}
        with tempfile.NamedTemporaryFile(dir=output_dir, prefix='.alpaca-', delete=False) as handle:
            candidate = Path(handle.name)
            handle.write(canonical(manifest))
        try:
            verify_bars_manifest(candidate)
        finally:
            candidate.unlink(missing_ok=True)
        path = immutable_json(manifest, output_dir, 'alpaca-stock-bars')
        temporary = cache.with_suffix('.pending')
        temporary.write_bytes(canonical({'manifest_relative_path': path.name, 'manifest_sha256': digest(path.read_bytes())}))
        temporary.replace(cache)
        return path
    except (AlpacaAccessError, ValueError, KeyError, TypeError, OSError) as exc:
        immutable = {'schema_version': 'alpaca-market-failure-v1', 'request': request,
                     'attempted_at': datetime.now(timezone.utc).isoformat(),
                     'http_status': getattr(exc, 'status_code', None), 'error_type': type(exc).__name__,
                     'automatic_retry_allowed': False, 'outcome_label': None, 'pages_received': pages}
        failure.write_bytes(canonical(immutable))
        raise
