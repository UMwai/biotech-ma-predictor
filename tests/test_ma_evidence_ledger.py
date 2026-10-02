"""Synthetic fixtures for the frame ledger join; invented values, not historical evidence."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'build_ma_evidence_ledger', Path(__file__).resolve().parents[1] / 'scripts' / 'build_ma_evidence_ledger.py')
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)

DATES = ['2021-01-01', '2023-01-01', '2024-01-01']


def coverage(ticker, day, cik, **extra):
    year = int(day[:4])
    row = {'ticker': ticker, 'observation_at': f'{day}T00:00:00+00:00', 'cik': cik,
           'horizon_end_at': f'{year + 1}-01-01T00:00:00+00:00' if day[5:] == '01-01' and year != 2024
           else '2024-12-31T00:00:00+00:00',
           'training_eligible': False, 'outcome_label': None, 'observation_disposition': None,
           'censoring_evidence': None, 'reviewed_positive_event_ids': [], 'reviewed_negative_corpus_sha256': None,
           'financial_record_id': None, 'financial_period_end': None, 'feature_max_available_at': None,
           'remaining_gaps': ['outcome_corpus_unreviewed_or_incomplete']}
    row.update(extra)
    return row


def fixture(**overrides):
    protocol = {'collection_order': ['KNOWN', 'ANON'], 'planned_observation_dates': DATES}
    frame = {'cohort_plan': {'observation_dates': DATES, 'horizon_days': 365},
             'records': [{'historical_ticker': 'KNOWN', 'historical_issuer_name': 'Known Bio Inc.', 'identity_status': 'unverified'},
                         {'historical_ticker': 'ANON', 'historical_issuer_name': 'Anon Therapeutics, Inc.', 'identity_status': 'unverified'}]}
    cov = [coverage('KNOWN', '2021-01-01', 11, training_eligible=True, outcome_label=1,
                    reviewed_positive_event_ids=['11:2021-03-01'], remaining_gaps=[]),
           coverage('KNOWN', '2023-01-01', 11, remaining_gaps=['prior_control_announcement_requires_historical_disposition_review']),
           coverage('KNOWN', '2024-01-01', 11, remaining_gaps=['prior_control_announcement_requires_historical_disposition_review']),
           coverage('ANON', '2021-01-01', None), coverage('ANON', '2023-01-01', None), coverage('ANON', '2024-01-01', None)]
    assembly = {'coverage': cov}
    panel = {'observations': [{'cik': 11, 'observation_at': '2021-01-01T00:00:00+00:00',
                               'label': {'event_class': 'change_of_control_announcement', 'review_id': 'r',
                                         'source_sha256': 'a' * 64, 'announcement_date': '2021-03-01'}}]}
    frozen = {'labels': [{'event_id': '11:2021-03-01', 'target_cik': 11, 'target_ticker': 'KNOWN',
                          'announcement_date': '2021-03-01', 'acquirer_name': 'Buyer', 'label': 'definitive'},
                         {'event_id': '99:2022-05-01', 'target_cik': 99, 'target_ticker': 'ANON',
                          'announcement_date': '2022-05-01', 'acquirer_name': 'Other', 'label': 'definitive'}]}
    candidates = [{'candidate_id': 'c1', 'target_cik': '', 'filer_name': 'ANON THERAPEUTICS INC',
                   'sec_signal_date': '2021-06-01', 'event_class': 'merger_proxy_filer', 'adjudication_status': 'pending_review'},
                  {'candidate_id': 'c2', 'target_cik': '11', 'filer_name': 'Known Bio', 'sec_signal_date': '2021-03-10',
                   'event_class': 'tender_offer_target', 'adjudication_status': 'provisional_primary_source'}]
    empty = {'sec_submission_collections': [], 'sec_review_queues': [], 'issuer_outcome_review_pointers': [],
             'issuer_archive_collections': [], 'regulatory_inventories': []}
    availability = {'tickers': {'KNOWN': empty, 'ANON': empty}}
    bars = {'KNOWN': [{'t': '2020-12-30T05:00:00Z'}], 'ANON': []}
    valuation = {d[:4]: {'bars_by_symbol': bars if d[:4] == '2021' else {}} for d in DATES}
    args = dict(protocol=protocol, frame=frame, assembly=assembly, panel=panel, frozen=frozen, candidates=candidates,
                financial_records=[], availability=availability, valuation=valuation,
                valuation_hashes={d[:4]: 'v' for d in DATES}, exclusion_refs={})
    args.update(overrides)
    return args


def test_statuses_identity_and_no_assigned_negatives():
    rows = ledger.build_rows(**fixture())
    status = {(r['ticker'], r['observation_date']): r for r in rows}
    assert [r['row_index'] for r in rows] == [1, 2, 3, 4, 5, 6]
    assert status[('KNOWN', '2021-01-01')]['ledger_status'] == 'admitted_positive'
    assert status[('KNOWN', '2023-01-01')]['ledger_status'] == 'prior_control_announcement_post_event_disposition_unreviewed'
    anon_2021 = status[('ANON', '2021-01-01')]
    assert anon_2021['ledger_status'] == 'sec_candidate_signal_in_horizon_unadjudicated'
    assert anon_2021['candidate_signals_in_horizon'][0]['match_basis'] == 'filer_name_only_identity_unverified'
    assert anon_2021['identity_unresolved'] and anon_2021['cik'] is None
    # A ticker-only reviewed event before the date never resolves identity or becomes a label.
    assert status[('ANON', '2023-01-01')]['ledger_status'] == 'prior_control_event_ticker_match_identity_unverified'
    assert all(r['negative_label_assigned_by_ledger'] is False and r['valuation_rating_supported'] is False for r in rows)
    assert [r['admitted_outcome_label'] for r in rows].count(0) == 0
    assert status[('KNOWN', '2021-01-01')]['vendor_bars_present'] and not anon_2021['vendor_bars_present']


@pytest.mark.parametrize('mutate, message', [
    (lambda a: a['assembly']['coverage'].pop(), 'coverage keys differ'),
    (lambda a: a['assembly']['coverage'].append(dict(a['assembly']['coverage'][0])), 'duplicate coverage row'),
    (lambda a: a['protocol'].update(collection_order=['ANON', 'KNOWN']), 'protocol order differs'),
    (lambda a: a['panel'].update(observations=[]), 'panel/coverage admission disagree'),
    (lambda a: a['valuation']['2021']['bars_by_symbol'].update(KNOWN=[{'t': '2021-01-01T05:00:00Z'}]), 'on/after observation'),
])
def test_rejects_drops_duplicates_reordering_and_late_quotes(mutate, message):
    args = fixture()
    mutate(args)
    with pytest.raises(ValueError, match=message):
        ledger.build_rows(**args)
