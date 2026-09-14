"""Join verified historical market features without changing reviewed outcomes."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.research.alpaca_data import verify_bars_manifest
from src.research.training import TrainingConfig, validate_training_data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _time(value: Any, name: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{name}: timezone-aware timestamp required') from exc
    _require(result.tzinfo is not None, f'{name}: timezone required')
    return result.astimezone(timezone.utc)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    _require(isinstance(value, dict), f'{path.name}: JSON object required')
    return value, _sha(raw)


def _local_file(root: Path, relative: Any) -> Path:
    _require(isinstance(relative, str) and bool(relative) and not Path(relative).is_absolute(),
             'market source requires a relative path')
    path = (root / relative).resolve()
    _require(path.is_relative_to(root.resolve()) and path.is_file(),
             'market source missing or outside collection directory')
    return path


def _symbols(value: Any) -> list[str]:
    _require(isinstance(value, list) and bool(value) and all(
        isinstance(ticker, str) and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}', ticker)
        for ticker in value), 'market symbols must be uppercase ticker strings')
    _require(len(set(value)) == len(value), 'duplicate market symbols')
    return sorted(value)


def _pre_test_support(rows: list[dict[str, Any]], test_start_year: int | None) -> dict[str, Any] | None:
    if test_start_year is None:
        return None
    TrainingConfig(test_start_year).validate()
    heldout = [row for row in rows if row['observation_at'].year == test_start_year]
    _require(bool(heldout), 'test_start_year has no observations')
    cutoff = min(row['cutoff'] for row in heldout)
    prior = [row for row in rows if row['observation_at'].year < test_start_year]
    usable = [row for row in prior if row['horizon_end'] <= cutoff and row['label_training_available_at'] <= cutoff]
    positives = len({row['event_id'] for row in usable if row['label']})
    negatives = len({row['cik'] for row in usable if not row['label']})
    return {'test_start_year': test_start_year, 'training_cutoff_at': cutoff.isoformat(),
            'structurally_admitted_prior_observations': len(prior),
            'company_observations': len(usable), 'distinct_positive_events': positives,
            'distinct_negative_companies': negatives, 'purged_prior_observations': len(prior) - len(usable),
            'purged_label_unavailable': sum(row['label_training_available_at'] > cutoff for row in prior),
            'minimum_distinct_positive_events': 5, 'minimum_distinct_negative_companies': 20,
            'remaining_positive_events': max(0, 5 - positives), 'remaining_negative_companies': max(0, 20 - negatives),
            'meets_training_support_floors': positives >= 5 and negatives >= 20,
            'availability_basis': 'mature horizon and effective label_training_available_at; market enrichment assigns no labels'}


def enrich_market_panel(dataset_path: Path, collection_path: Path, *, now: datetime | None = None,
                        test_start_year: int | None = None) -> dict[str, Any]:
    """Return a separate enriched panel and coverage report from read-only inputs.

    A complete collection inventory includes both successful and explicitly
    failed windows. Missing bars or failed windows never remove company rows.
    """
    from src.research.market_features import FEATURE_UNITS as MARKET_FEATURE_UNITS, calculate_market_features, required_history_start
    from src.research.market_contract import market_feature_contract

    current = _time(now or datetime.now(timezone.utc), 'now')
    _require(current <= datetime.now(timezone.utc), 'market assembly freeze is in the future')
    base, base_hash = _load(Path(dataset_path))
    validate_training_data(base, now=current)
    _require('market_enrichment' not in base, 'dataset is already market enriched')
    collection_path = Path(collection_path).resolve()
    collection, collection_hash = _load(collection_path)
    _require(collection.get('schema_version') == 'alpaca-panel-market-collection-v1', 'unsupported market collection schema')
    _require(collection.get('base_panel_sha256') == base_hash, 'market collection base panel SHA-256 mismatch')
    _require(collection.get('model_training_performed') is False, 'collection must not claim model training')
    _require(collection.get('feed') in {'sip', 'iex'}, 'market enrichment requires one explicit SIP or IEX feed')
    collected = _time(collection.get('collected_at'), 'collection collected_at')
    _require(collected <= current, 'market collection retrieval follows current time')
    _require(not (set(base['feature_names']) & set(MARKET_FEATURE_UNITS)), 'market feature name collides with base features')

    expected: dict[datetime, dict[str, int]] = {}
    for row in base['observations']:
        ticker = _symbols([row.get('ticker')])[0]
        member = row['membership']
        _require(member.get('ticker') == ticker and str(member.get('cik')) == str(row['cik']),
                 'reviewed membership must bind the row ticker and CIK')
        cutoff = _time(row['information_cutoff_at'], 'information_cutoff_at')
        group = expected.setdefault(cutoff, {})
        _require(ticker not in group or group[ticker] == int(row['cik']),
                 'one cutoff maps a ticker to multiple company identities')
        group[ticker] = int(row['cik'])

    groups: dict[datetime, dict[str, Any]] = {}
    successful = collection.get('collections')
    gaps = collection.get('gaps', [])
    _require(isinstance(successful, list) and isinstance(gaps, list), 'collection windows and gaps must be lists')
    for failed, entries in ((False, successful), (True, gaps)):
        for entry in entries:
            _require(isinstance(entry, dict), 'market window must be an object')
            cutoff = _time(entry.get('information_cutoff_at'), 'market window cutoff')
            _require(cutoff in expected and cutoff not in groups, 'extra or duplicate market cutoff group')
            symbols = _symbols(entry.get('symbols'))
            _require(symbols == sorted(expected[cutoff]), 'market window symbols differ from base observation inventory')
            asof = cutoff.date().isoformat()
            _require(entry.get('asof') == asof, 'market window asof differs from historical cutoff date')
            if failed:
                _require(isinstance(entry.get('reason'), str) and bool(entry['reason'].strip()), 'failed market window requires a reason')
                _require('bars_manifest_relative_path' not in entry, 'failed window cannot also supply a successful manifest')
                groups[cutoff] = {'gap': copy.deepcopy(entry), 'manifest': None}
                continue
            path = _local_file(collection_path.parent, entry.get('bars_manifest_relative_path'))
            digest = _sha(path.read_bytes())
            _require(digest == entry.get('bars_manifest_sha256'), 'bars manifest SHA-256 mismatch')
            manifest = verify_bars_manifest(path)
            _require(manifest.get('schema_version') == 'alpaca-stock-bars-v1' and manifest.get('query_complete') is True,
                     'bars manifest query is incomplete')
            _require(manifest.get('original_vendor_vintage_archived') is False,
                     'historical bars must not claim original vendor vintage')
            request = manifest.get('request', {})
            _require(_symbols(request.get('symbols')) == symbols, 'bars request symbols differ from declared window')
            _require(request.get('asof') == asof, 'bars request asof differs from historical cutoff date')
            _require(_time(request.get('end'), 'bars request end') == cutoff, 'bars request end differs from information cutoff')
            required_start = required_history_start(cutoff.isoformat())
            _require(required_start is not None, 'feature lookback is outside supported market calendar')
            _require(_time(request.get('start'), 'bars request start') <= _time(required_start + 'T00:00:00Z', 'required market history start'),
                     'bars request start does not cover feature lookback')
            _require(request.get('feed') == collection['feed'] and request.get('adjustment') == 'raw'
                     and request.get('timeframe') == '1Day' and request.get('currency') == 'USD',
                     'bars request must use the same declared feed, raw daily bars and USD')
            retrieval = _time(manifest.get('retrieved_at'), 'bars retrieved_at')
            _require(cutoff <= retrieval <= collected, 'bars retrieval clock is inconsistent with cutoff or collection')
            pages = manifest.get('pages')
            _require(isinstance(pages, list) and bool(pages), 'bars source pages missing')
            page_times = []
            for page in pages:
                _require(isinstance(page, dict), 'bars page receipt must be an object')
                source_path = _local_file(path.parent, page.get('source_relative_path'))
                _require(source_path.is_relative_to(collection_path.parent), 'bars page escapes collection directory')
                page_time = _time(page.get('retrieved_at'), 'bars page retrieved_at')
                _require(cutoff <= page_time <= retrieval, 'bars page retrieval clock is inconsistent')
                page_times.append(page_time)
            _require(max(page_times) == retrieval, 'bars manifest latest retrieval does not match its pages')
            bars = manifest.get('bars_by_symbol')
            _require(isinstance(bars, dict) and not (set(bars) - set(symbols)), 'bars contain an unrequested symbol')
            groups[cutoff] = {'manifest': manifest, 'manifest_relative_path': str(path.relative_to(collection_path.parent)),
                              'manifest_sha256': digest, 'gap': None}
    _require(set(groups) == set(expected), 'market collection omits an expected cutoff group')

    enriched = copy.deepcopy(base)
    enriched['feature_names'] = list(base['feature_names']) + list(MARKET_FEATURE_UNITS)
    enriched['feature_units'] = {**base['feature_units'], **MARKET_FEATURE_UNITS}
    enriched['market_data_contract'] = market_feature_contract(collection['feed'])
    coverage = []
    for original, row in zip(base['observations'], enriched['observations']):
        cutoff = _time(row['information_cutoff_at'], 'row cutoff')
        group = groups[cutoff]
        member_from = _time(row['membership']['valid_from'], 'membership valid_from')
        raw_bars = group['manifest']['bars_by_symbol'].get(row['ticker'], []) if group['manifest'] else []
        _require(isinstance(raw_bars, list), 'bars for a symbol must be a list')
        bars = [bar for bar in raw_bars if _time(bar.get('t'), 'bar timestamp') >= member_from]
        calculation = calculate_market_features(bars, cutoff.isoformat(), feed=collection['feed'], adjustment='raw')
        _require(calculation.get('units') == MARKET_FEATURE_UNITS and
                 set(calculation.get('features', {})) == set(MARKET_FEATURE_UNITS), 'market calculation feature contract differs')
        market_available = (calculation.get('provenance', {}).get('last_completed_bar_available_at')
                            if any(value is not None for value in calculation['features'].values()) else None)
        combined_available = _time(original['feature_max_available_at'], 'financial availability')
        if market_available is not None:
            market_available = _time(market_available, 'market feature availability')
            _require(market_available <= cutoff, 'market feature availability follows cutoff')
            combined_available = max(combined_available, market_available)
        row['features'].update(calculation['features'])
        row['feature_max_available_at'] = combined_available.isoformat()
        evidence = {'provider': 'Alpaca', 'feed': collection['feed'],
                    'base_panel_sha256': base_hash, 'collection_sha256': collection_hash,
                    'bars_manifest_relative_path': group.get('manifest_relative_path'),
                    'bars_manifest_sha256': group.get('manifest_sha256'),
                    'retrieved_at': group['manifest']['retrieved_at'] if group['manifest'] else None,
                    'collection_collected_at': collected.isoformat(),
                    'original_vendor_vintage_archived': False, 'asof_is_identity_date_only': True,
                    'source_feed_identity_verified': group['manifest'] is not None,
                    'identity_basis': {'ticker': row['ticker'], 'cik': row['cik'],
                        'membership_source_uri': row['membership']['source_uri'],
                        'membership_source_sha256': row['membership']['source_sha256'],
                        'valid_from': row['membership']['valid_from'],
                        'claim': 'CIK identity comes from reviewed base membership; Alpaca bars contain no CIK'},
                    'bars_before_membership_excluded': len(raw_bars) - len(bars),
                    'collection_gap': group['gap'], 'calculation': calculation}
        row['market_evidence'] = evidence
        coverage.append({'ticker': row['ticker'], 'cik': row['cik'], 'observation_at': row['observation_at'],
                         'information_cutoff_at': row['information_cutoff_at'],
                         'feed': collection['feed'],
                         'market_coverage_scope': 'consolidated_us_exchanges' if collection['feed'] == 'sip' else 'iex_venue_only',
                         'market_feature_values_present': sum(value is not None for value in calculation['features'].values()),
                         'market_feature_count': len(MARKET_FEATURE_UNITS), 'collection_gap': group['gap'],
                         'bars_before_membership_excluded': len(raw_bars) - len(bars),
                         'market_feature_history': calculation.get('feature_history'),
                         'quality_flags': calculation.get('quality_flags'),
                         'label_and_membership_preserved': row['label'] == original['label'] and row['membership'] == original['membership']})
    metadata = {'schema_version': 'alpaca-market-enrichment-provenance-v1',
                'generated_at': current.isoformat(), 'base_panel_sha256': base_hash,
                'base_data_as_of': base['data_as_of'],
                'data_as_of_basis': 'actual_enrichment_assembly_freeze',
                'market_collection_sha256': collection_hash, 'collected_at': collected.isoformat(),
                'feed': collection['feed'],
                'market_coverage_scope': 'consolidated_us_exchanges' if collection['feed'] == 'sip' else 'iex_venue_only',
                'original_vendor_vintage_archived': False, 'labels_created': 0, 'observations_removed': 0,
                'availability_semantics': 'Historical daily completion is reconstructed; actual retrieval remains separate and original vendor vintage is not proven'}
    enriched['market_enrichment'] = metadata
    # New vendor bytes cannot be placed under an older dataset information
    # freeze. Retain the base freeze separately; all row-level clocks stay intact.
    enriched['data_as_of'] = current.isoformat()
    _, normalized = validate_training_data(enriched, now=current)
    with_features = sum(row['market_feature_values_present'] > 0 for row in coverage)
    fully_covered = all(row['market_feature_values_present'] == len(MARKET_FEATURE_UNITS) for row in coverage)
    status = ('market_data_unavailable' if not with_features else
              'market_features_assembled_for_training_checks' if fully_covered else 'market_features_assembled_with_gaps')
    return {'schema_version': 'alpaca-market-panel-assembly-v1', 'generated_at': current.isoformat(),
            'status': status, 'model_training_performed': False,
            'validated_predictive_edge': False, 'base_panel_sha256': base_hash,
            'market_collection_sha256': collection_hash, 'base_observations': len(base['observations']),
            'feed': collection['feed'], 'market_coverage_scope': metadata['market_coverage_scope'],
            'enriched_observations': len(enriched['observations']), 'market_feature_names': list(MARKET_FEATURE_UNITS),
            'successful_collection_windows': len(successful), 'failed_collection_windows': len(gaps),
            'observations_with_market_features': with_features,
            'observations_without_market_features': sum(row['market_feature_values_present'] == 0 for row in coverage),
            'pre_test_training_support': _pre_test_support(normalized, test_start_year),
            'original_vendor_vintage_archived': False, 'coverage': coverage, 'panel': enriched}
