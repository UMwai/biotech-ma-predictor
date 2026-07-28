from datetime import date
import urllib.error

import pytest

from src.research.deal_labels import (
    build_annual_risk_set,
    build_deal_candidates,
    parse_sec_display_name,
    sec_archive_url,
    validate_candidate_ledger,
)
from src.research.evaluator import (
    evaluate_clinical_assets,
    evaluate_companies,
    evaluate_orange_book_assets,
)
from src.research.matching import CompanyMatcher, normalize_organization
from src.research.metrics import RankedObservation, evaluate_rare_event_ranking
from src.research.models import PublicCompany
from src.research.sources import HttpCache, parse_fda_date, parse_number


def sample_company() -> PublicCompany:
    return PublicCompany(
        ticker="ACME",
        name="Acme Therapeutics, Inc. Common Stock",
        exchange="US-listed",
        industry="Biotechnology: Pharmaceutical Preparations",
        market_cap_usd=1_200_000_000,
        cik=123456,
    )


def test_source_value_parsers():
    assert parse_number("$1,234.50") == 1234.50
    assert parse_number("N/A") is None
    assert parse_fda_date("Jul 22, 2030") == date(2030, 7, 22)


def test_http_cache_retries_transient_server_errors(tmp_path, monkeypatch):
    calls = 0

    class Response:
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(request.full_url, 500, "temporary", {}, None)
        return Response()

    monkeypatch.setattr("src.research.sources.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("src.research.sources.time.sleep", lambda _: None)
    cache = HttpCache(tmp_path, "test-agent")
    assert cache.get_json("https://example.test/data", "retry", max_attempts=2) == {
        "ok": True
    }
    assert calls == 2


def test_organization_normalization_and_matching():
    assert (
        normalize_organization("Acme Therapeutics, Inc. Common Stock")
        == "ACME THERAPEUTICS"
    )
    matcher = CompanyMatcher([sample_company()])
    match = matcher.match("ACME THERAPEUTICS INC")
    assert match.ticker == "ACME"
    assert match.confidence == 1.0


def test_orange_book_evaluation_rewards_innovator_protection():
    matcher = CompanyMatcher([sample_company()])
    raw = [
        {
            "ingredient": "ACMEZUMAB",
            "applicant": "Acme Therapeutics Inc",
            "trade_names": ["AcmeDrug"],
            "routes": ["INJECTION;INTRAVENOUS"],
            "application_numbers": ["123456"],
            "application_types": ["N"],
            "approval_dates": [date(2025, 1, 1)],
            "is_reference_drug": True,
            "patent_expiries": [date(2035, 1, 1)],
            "exclusivity_expiries": [date(2032, 1, 1)],
            "patent_numbers": ["9999999"],
            "product_rows": 2,
            "applicant_count_for_ingredient": 1,
        }
    ]
    result = evaluate_orange_book_assets(raw, matcher, date(2026, 7, 22))[0]
    assert result.owner_ticker == "ACME"
    assert result.score >= 80
    assert result.patent_expiry == "2035-01-01"


def test_clinical_and_company_evaluation():
    company = sample_company()
    matcher = CompanyMatcher([company])
    clinical = [
        {
            "name": "ACM-101",
            "sponsor": "Acme Therapeutics Inc",
            "intervention_type": "DRUG",
            "nct_ids": ["NCT00000001", "NCT00000002"],
            "phases": ["PHASE3"],
            "conditions": ["Rare disease"],
            "statuses": ["RECRUITING"],
            "last_updates": ["2026-06-01"],
            "enrollments": [120],
            "trial_count": 2,
        }
    ]
    asset = evaluate_clinical_assets(clinical, matcher, date(2026, 7, 22))[0]
    evaluations = evaluate_companies(
        [company],
        [asset],
        "2026-07-22T12:00:00+00:00",
        announced_target_ciks={
            123456: [{"form": "SC 14D9", "file_date": "2026-06-01"}],
        },
    )
    assert asset.owner_ticker == "ACME"
    assert asset.score > 60
    assert evaluations[0].clinical_asset_count == 1
    assert evaluations[0].research_score > 60
    assert evaluations[0].risk_set_eligible is False
    assert "SC 14D9" in evaluations[0].risk_set_exclusion_reason


def test_sec_display_name_and_archive_url():
    name, tickers = parse_sec_display_name(
        ["Example Therapeutics, Inc.  (EXMP, EXMPW)  (CIK 0000123456)"]
    )
    assert name == "Example Therapeutics, Inc."
    assert tickers == ["EXMP", "EXMPW"]
    assert sec_archive_url(
        123456,
        "0000123456-26-000001",
        "0000123456-26-000001:sc14d9.htm",
    ) == (
        "https://www.sec.gov/Archives/edgar/data/123456/"
        "000012345626000001/sc14d9.htm"
    )


def test_deal_candidates_distinguish_target_signal_from_review_queue():
    filings = [
        {
            "_id": "0001-26-000001:sc14d9.htm",
            "ciks": ["0000000001"],
            "sics": ["2834"],
            "display_names": ["Target Bio, Inc.  (TGT)  (CIK 0000000001)"],
            "file_date": "2026-01-10",
            "form": "SC 14D9",
            "adsh": "0001-26-000001",
        },
        {
            "_id": "0001-26-000002:sc14d9a.htm",
            "ciks": ["0000000001"],
            "sics": ["2834"],
            "display_names": ["Target Bio, Inc.  (TGT)  (CIK 0000000001)"],
            "file_date": "2026-01-20",
            "form": "SC 14D9/A",
            "adsh": "0001-26-000002",
        },
        {
            "_id": "0002-26-000001:defm14a.htm",
            "ciks": ["0000000002"],
            "sics": ["2836"],
            "display_names": ["Proxy Bio Corp.  (PRXY)  (CIK 0000000002)"],
            "file_date": "2026-02-01",
            "form": "DEFM14A",
            "adsh": "0002-26-000001",
        },
        {
            "_id": "0003-26-000001:defm14a.htm",
            "ciks": ["0000000003"],
            "sics": ["7371"],
            "display_names": ["Software Corp.  (SOFT)  (CIK 0000000003)"],
            "file_date": "2026-02-01",
            "form": "DEFM14A",
            "adsh": "0003-26-000001",
        },
    ]
    candidates = build_deal_candidates(filings)
    assert len(candidates) == 2
    target = next(item for item in candidates if item.target_cik == 1)
    proxy = next(item for item in candidates if item.target_cik == 2)
    assert target.event_class == "tender_offer_target"
    assert target.confidence == "high"
    assert target.filing_count == 2
    assert target.model_label_eligible is False
    assert proxy.event_class == "merger_proxy_filer"
    assert proxy.adjudication_status == "pending_review"
    assert validate_candidate_ledger(candidates)["rows"] == 2


def test_annual_risk_set_uses_contemporaneous_filers_and_forward_signals():
    filings = [
        {
            "_id": "annual-1",
            "ciks": ["0000000001"],
            "sics": ["2834"],
            "file_num": ["001-12345"],
            "display_names": ["Target Bio, Inc.  (TGT)  (CIK 0000000001)"],
            "file_date": "2024-03-01",
            "form": "10-K",
            "adsh": "annual-1",
        },
        {
            "_id": "annual-2",
            "ciks": ["0000000002"],
            "sics": ["2836"],
            "file_num": ["001-54321"],
            "display_names": ["Control Bio, Inc.  (CTRL)  (CIK 0000000002)"],
            "file_date": "2024-02-15",
            "form": "10-K",
            "adsh": "annual-2",
        },
        {
            "_id": "otc",
            "ciks": ["0000000003"],
            "sics": ["2834"],
            "file_num": ["000-11111"],
            "display_names": ["OTC Bio, Inc.  (CIK 0000000003)"],
            "file_date": "2024-02-15",
            "form": "10-K",
            "adsh": "annual-3",
        },
    ]
    candidates = build_deal_candidates(
        [
            {
                "_id": "0001-25-000001:sc14d9.htm",
                "ciks": ["0000000001"],
                "sics": ["2834"],
                "display_names": ["Target Bio, Inc.  (TGT)  (CIK 0000000001)"],
                "file_date": "2025-06-01",
                "form": "SC 14D9",
                "adsh": "0001-25-000001",
            }
        ]
    )
    rows, exclusions = build_annual_risk_set(
        filings,
        candidates,
        data_end_date=date(2026, 7, 22),
    )
    assert not exclusions
    assert len(rows) == 2
    target = next(row for row in rows if row["cik"] == 1)
    control = next(row for row in rows if row["cik"] == 2)
    assert target["provisional_tender_offer_signal_within_horizon"] is True
    assert target["outcome_window_complete"] is True
    assert target["model_label_eligible"] is False
    assert control["provisional_any_transaction_signal_within_horizon"] is False


def test_rare_event_metrics_do_not_treat_scores_as_probabilities():
    observations = [
        RankedObservation("a", score=90, label=True),
        RankedObservation("b", score=80, label=False),
        RankedObservation("c", score=70, label=True),
        RankedObservation("d", score=60, label=False),
    ]
    result = evaluate_rare_event_ranking(observations, cutoffs=(2,))
    assert result["base_rate"] == 0.5
    assert result["average_precision"] == (1.0 + 2 / 3) / 2
    assert result["top_k"]["2"]["precision"] == 0.5
    assert result["top_k"]["2"]["lift_over_base_rate"] == 1.0
    assert result["probability_metrics"] is None


def test_rare_event_metrics_emit_probability_quality_only_when_supplied():
    observations = [
        RankedObservation("a", score=0.8, probability=0.8, label=True),
        RankedObservation("b", score=0.2, probability=0.2, label=False),
    ]
    metrics = evaluate_rare_event_ranking(observations)
    assert metrics["probability_metrics"]["brier_score"] == pytest.approx(0.04)
