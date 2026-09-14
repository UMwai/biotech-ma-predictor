"""Synthetic bar fixtures test arithmetic and integrity, never model evidence."""

from copy import deepcopy
from datetime import date, datetime, time, timedelta
import json
import math
from zoneinfo import ZoneInfo

import pytest

from src.research.market_features import calculate_market_features, required_history_start

NY = ZoneInfo("America/New_York")
CUTOFF = "2021-05-15T04:00:00Z"
RET21 = "raw_price_return_21_sessions"
RET63 = "raw_price_return_63_sessions"
VOL63 = "raw_price_volatility_63_sessions"
DD63 = "raw_price_drawdown_63_sessions"
DV21 = "mean_dollar_volume_21_sessions"


def bar_on(day, close=100.0, volume=1000):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    return {"t": datetime.combine(day, time.min, NY).isoformat(),
            "o": close, "h": close * 1.01, "l": close * 0.99, "c": close,
            "v": volume, "n": 100, "vw": close}


@pytest.fixture
def bars():
    # Fixed dates independent of the implementation's exchange-calendar helper.
    holidays = {date(2021, 1, 18), date(2021, 2, 15), date(2021, 4, 2)}
    start, end = date(2021, 1, 4), date(2021, 5, 14)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    sessions = [day for day in days if day.weekday() < 5 and day not in holidays][-70:]
    return [bar_on(day, 100 * 1.002 ** i, 1000 + i) for i, day in enumerate(sessions)]


def calculate(bars, cutoff=CUTOFF, **kwargs):
    return calculate_market_features(bars, cutoff, feed=kwargs.pop("feed", "sip"), **kwargs)


def scale_bars(bars, start, factor):
    result = deepcopy(bars)
    for bar in result[start:]:
        for key in ("o", "h", "l", "c", "vw"):
            bar[key] *= factor
    return result


def test_complete_history_has_declared_arithmetic_units_and_no_admission(bars):
    result = calculate(bars)
    values = result["features"]
    assert values[RET21] == pytest.approx(1.002 ** 21 - 1)
    assert values[RET63] == pytest.approx(1.002 ** 63 - 1)
    assert values[VOL63] == pytest.approx(0, abs=1e-12)
    assert values[DD63] == 0
    assert values[DV21] == pytest.approx(sum(b["c"] * b["v"] for b in bars[-21:]) / 21)
    assert result["all_features_available"] is True
    assert result["quality_flags"] == []
    assert result["units"] == {RET21: "ratio", RET63: "ratio", VOL63: "annualized_ratio",
                                DV21: "USD_per_session", DD63: "ratio"}
    assert result["price_basis"] == "unadjusted"
    assert result["corporate_actions_verified"] is False
    assert result["provenance"]["historical_publication_proof"] is False
    assert result["provenance"]["feed_identity_verified"] is False
    assert not {"label", "market_cap", "training_allowed"} & result.keys()
    json.dumps(result, allow_nan=False)


def test_sample_log_volatility_and_maximum_drawdown_are_unambiguous(bars):
    closes = [100.0]
    for i in range(1, len(bars)):
        closes.append(closes[-1] * math.exp(0.01 if i % 2 == 0 else -0.01))
    altered = [bar_on(datetime.fromisoformat(b["t"]).date(), c) for b, c in zip(bars, closes)]
    values = calculate(altered)["features"]
    # 63 alternating +/- .01 log changes have sample annualized stdev .16.
    assert values[VOL63] == pytest.approx(0.16)
    assert values[DD63] == pytest.approx(math.exp(-0.01) - 1)


def test_current_day_bar_waits_until_next_new_york_midnight(bars):
    before = calculate(bars, "2021-05-15T03:59:59Z")
    after = calculate(bars)
    assert before["provenance"]["last_completed_session_date"] == "2021-05-13"
    assert before["provenance"]["excluded_incomplete_or_future_bar_count"] == 1
    assert after["provenance"]["last_completed_session_date"] == "2021-05-14"
    assert after["provenance"]["last_completed_bar_available_at"] == "2021-05-15T04:00:00+00:00"


@pytest.mark.parametrize("day,cutoff,available", [
    ("2021-03-12", "2021-03-15T13:30:00Z", "2021-03-13T05:00:00+00:00"),
    ("2021-03-15", "2021-03-16T04:00:00Z", "2021-03-16T04:00:00+00:00"),
    ("2021-11-05", "2021-11-08T14:30:00Z", "2021-11-06T04:00:00+00:00"),
    ("2021-11-08", "2021-11-09T05:00:00Z", "2021-11-09T05:00:00+00:00"),
])
def test_daily_availability_uses_new_york_dst(day, cutoff, available):
    result = calculate([bar_on(day)], cutoff)
    assert result["provenance"]["last_completed_bar_available_at"] == available
    assert "stale_last_completed_bar" not in result["quality_flags"]


def test_future_prices_do_not_change_features_or_completed_input_hash(bars):
    before = calculate(bars)
    after = calculate(bars + [bar_on("2021-05-17", 1e8)])
    assert before["features"] == after["features"]
    assert before["quality_flags"] == after["quality_flags"]
    assert before["provenance"]["normalized_completed_bars_sha256"] == after["provenance"]["normalized_completed_bars_sha256"]


def test_missing_session_is_not_silently_replaced_by_an_older_bar(bars):
    missing = bars[-30]
    result = calculate([b for b in bars if b is not missing])
    assert result["features"][RET21] is not None
    assert result["features"][DV21] is not None
    for name in (RET63, VOL63, DD63):
        assert result["features"][name] is None
        assert "missing_expected_sessions" in result["feature_history"][name]["gaps"]
        assert datetime.fromisoformat(missing["t"]).date().isoformat() in result["feature_history"][name]["missing_session_dates"]


def test_stale_history_cannot_be_presented_as_current(bars):
    result = calculate(bars[:-1])
    assert set(result["features"].values()) == {None}
    assert "stale_last_completed_bar" in result["quality_flags"]
    assert result["provenance"]["latest_expected_completed_session_date"] == "2021-05-14"
    assert result["provenance"]["last_completed_session_date"] == "2021-05-13"


def test_each_feature_needs_its_own_full_history(bars):
    result = calculate(bars[-21:])
    assert result["features"][DV21] is not None
    assert result["features"][RET21] is None  # 21 intervals require 22 closes.
    assert "insufficient_history" in result["feature_history"][RET21]["gaps"]
    assert result["feature_history"][RET63]["required_bars"] == 64


def test_empty_bars_are_unknown_not_zero():
    result = calculate([])
    assert set(result["features"].values()) == {None}
    assert "no_completed_bars" in result["quality_flags"]
    assert result["provenance"]["last_completed_bar_available_at"] is None


def test_observed_zero_volume_is_valid_and_not_a_missing_bar(bars):
    for bar in bars:
        bar["v"] = 0
        bar["n"] = 0
    result = calculate(bars)
    assert result["all_features_available"] is True
    assert result["features"][DV21] == 0


def test_null_optional_alpaca_fields_are_treated_as_absent(bars):
    null_fields = [dict(bar, n=None, vw=None) for bar in bars]
    missing_fields = [{key: value for key, value in bar.items() if key not in {"n", "vw"}} for bar in bars]
    assert calculate(null_fields) == calculate(missing_fields)
    assert calculate(null_fields)["all_features_available"] is True


@pytest.mark.parametrize("factor", [0.49, 0.5, 2.0, 2.01])
def test_raw_split_like_jump_nulls_affected_price_windows(bars, factor):
    # Use a constant base so exact 0.5/2.0 boundaries are tested precisely.
    constant = [bar_on(datetime.fromisoformat(b["t"]).date()) for b in bars]
    result = calculate(scale_bars(constant, -10, factor))
    for name in (RET21, RET63, VOL63, DD63):
        assert result["features"][name] is None
        assert "corporate_action_discontinuity" in result["feature_history"][name]["gaps"]
    assert result["features"][DV21] is not None


def test_old_discontinuity_does_not_block_shorter_unaffected_window(bars):
    result = calculate(scale_bars(bars, 30, 10))
    assert result["features"][RET21] is not None
    assert result["features"][RET63] is None
    assert result["features"][VOL63] is None
    assert result["features"][DD63] is None


@pytest.mark.parametrize("key,value,reason", [
    ("c", float("nan"), "finite"), ("v", float("inf"), "finite"),
    ("o", 0, "positive"), ("l", -1, "positive"), ("v", -1, "nonnegative"),
    ("h", 1, "impossible OHLC"), ("l", 10000, "impossible OHLC"),
    ("n", -1, "nonnegative"), ("n", 0.5, "integer"), ("n", float("nan"), "finite"),
    ("vw", float("inf"), "finite"), ("c", True, "finite"), ("v", "1000", "finite"),
    ("feed", "iex", "differs"), ("adjustment", "split", "differs"),
    ("t", "2021-05-14T00:00:00", "timezone"),
])
def test_invalid_bars_are_rejected_before_calculation(bars, key, value, reason):
    bars[-1][key] = value
    with pytest.raises(ValueError, match=reason):
        calculate(bars)


def test_required_fields_and_duplicate_market_dates_are_rejected(bars):
    duplicate = dict(bars[-1], t="2021-05-14T05:00:00Z")
    with pytest.raises(ValueError, match="duplicate daily bar"):
        calculate(bars + [duplicate])
    del bars[-1]["c"]
    with pytest.raises(ValueError, match="missing a required"):
        calculate(bars)


@pytest.mark.parametrize("feed", ["", "auto", "SIP", "sip,iex", None])
def test_feed_must_be_explicit_without_blending(feed):
    with pytest.raises(ValueError, match="feed must"):
        calculate([], feed=feed)


def test_adjusted_inputs_and_naive_cutoffs_are_rejected(bars):
    with pytest.raises(ValueError, match="only raw"):
        calculate(bars, adjustment="all")
    with pytest.raises(ValueError, match="timezone"):
        calculate(bars, "2021-05-15T00:00:00")


def test_feed_is_preserved_and_input_order_does_not_change_results(bars):
    original = deepcopy(bars)
    result = calculate(bars, feed="iex")
    reversed_result = calculate(list(reversed(bars)), feed="iex")
    assert result == reversed_result
    assert result["feed"] == "iex"
    assert bars == original


@pytest.mark.parametrize("last_session,cutoff", [
    ("2021-12-31", "2022-01-01T05:00:00Z"),  # Saturday New Year does not close Friday.
    ("2021-06-18", "2021-06-19T04:00:00Z"),  # Juneteenth not yet exchange holiday.
    ("2022-06-17", "2022-06-21T04:00:00Z"),  # Observed Juneteenth Monday closed.
    ("2021-04-01", "2021-04-03T04:00:00Z"),  # Good Friday.
    ("2018-12-04", "2018-12-06T05:00:00Z"),  # Bush national mourning.
    ("2025-01-08", "2025-01-10T05:00:00Z"),  # Carter national mourning.
    ("2021-11-26", "2021-11-27T05:00:00Z"),  # Early close still a session.
])
def test_full_day_calendar_rules_avoid_false_staleness(last_session, cutoff):
    result = calculate([bar_on(last_session)], cutoff)
    assert result["provenance"]["latest_expected_completed_session_date"] == last_session
    assert "stale_last_completed_bar" not in result["quality_flags"]


@pytest.mark.parametrize("day", ["2018-12-05", "2025-01-09", "2022-06-20", "2021-04-02", "2021-05-15"])
def test_impossible_holiday_or_weekend_daily_bar_is_rejected(day):
    with pytest.raises(ValueError, match="non-session date"):
        calculate([bar_on(day)])


@pytest.mark.parametrize("cutoff", ["2015-05-15T04:00:00Z", "2027-01-04T05:00:00Z"])
def test_outside_calendar_scope_stays_unavailable(cutoff):
    result = calculate([], cutoff)
    assert "unsupported_calendar_scope" in result["quality_flags"]
    assert set(result["features"].values()) == {None}
    assert required_history_start(cutoff) is None


def test_collection_history_start_is_the_required_first_session(bars):
    result = calculate(bars)
    assert required_history_start(CUTOFF) == datetime.fromisoformat(bars[-64]["t"]).date().isoformat()
    assert required_history_start(CUTOFF) == result["feature_history"][RET63]["window_start_date"]
