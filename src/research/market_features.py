"""Conservative features from one declared feed of unadjusted US daily bars.

This module performs no I/O and grants no label or model admission. A missing bar
is a coverage gap, never evidence of a negative acquisition outcome. Next New
York midnight is an availability *policy*, not proof that today's provider copy
was published in that form historically. Raw close changes are not economic,
split-adjusted, dividend-adjusted, or total returns.

The bounded 2016–2026 full-day calendar is a research policy, not issuer listing
or provider trading-status evidence. Early closes still count as sessions.
Rules and exceptional closures were checked against primary sources:
https://www.nyse.com/trade/hours-calendars
https://www.nyse.com/publicdocs/nyse/regulation/nyse/NYSE_Rules.pdf
https://www.sec.gov/file/34-93183
https://ir.theice.com/press/news-details/2021/NYSE-Group-Announces-2022-2023-and-2024-Holiday-and-Early-Closings-Calendar/default.aspx
https://ir.theice.com/press/news-details/2018/New-York-Stock-Exchange-to-Honor-President-George-H-W-Bush/default.aspx
https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf
Saturday New Year's Day does not close the preceding Friday; Juneteenth starts
in 2022. Unexpected future closures or issuer-specific suspensions require new
source evidence; this calendar cannot establish either was absent.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
import statistics
from zoneinfo import ZoneInfo

MARKET_TIMEZONE = ZoneInfo("America/New_York")
CALENDAR_START = date(2016, 1, 1)
CALENDAR_END = date(2026, 12, 31)
CALENDAR_POLICY_VERSION = "us-equity-full-day-2016-2026-v1"
FEATURE_UNITS = {
    "raw_price_return_21_sessions": "ratio",
    "raw_price_return_63_sessions": "ratio",
    "raw_price_volatility_63_sessions": "annualized_ratio",
    "mean_dollar_volume_21_sessions": "USD_per_session",
    "raw_price_drawdown_63_sessions": "ratio",
}
_REQUIRED_BARS = dict(zip(FEATURE_UNITS, (22, 64, 64, 21, 63)))
_EXTRA_CLOSURES = {date(2018, 12, 5), date(2025, 1, 9)}


def _timestamp(value: str, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must have an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if number < 0 or (positive and number == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return number


def _weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def _easter(year: int) -> date:
    # Gregorian computus; used only for the full-day Good Friday closure.
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    value = h + l - 7 * m + 114
    return date(year, value // 31, value % 31 + 1)


def _observed(day: date) -> date:
    return day + timedelta(days=-1 if day.weekday() == 5 else 1 if day.weekday() == 6 else 0)


@lru_cache(maxsize=11)
def _holidays(year: int) -> frozenset[date]:
    new_year = date(year, 1, 1)
    memorial = date(year, 5, 31)
    holidays = {
        new_year + timedelta(days=1 if new_year.weekday() == 6 else 0),
        _weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter(year) - timedelta(days=2),
        memorial - timedelta(days=memorial.weekday()),
        _observed(date(year, 7, 4)),
        _weekday(year, 9, 0, 1),
        _weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    return frozenset(holidays | {day for day in _EXTRA_CLOSURES if day.year == year})


def _session(day: date) -> bool:
    return day.weekday() < 5 and day not in _holidays(day.year)


def _available_at(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, MARKET_TIMEZONE).astimezone(timezone.utc)


def _expected_sessions(prior_day: date, required: int) -> list[date]:
    if not CALENDAR_START <= prior_day <= CALENDAR_END:
        return []
    found = []
    cursor = prior_day
    while len(found) < required and cursor >= CALENDAR_START:
        if _session(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(found))


def required_history_start(information_cutoff_at: str) -> str | None:
    """Earliest of the 64 required sessions, or None outside calendar coverage.

    This is a session date in America/New_York, not a UTC request timestamp or
    proof of the security's membership. Callers must still verify source coverage.
    """
    cutoff_date = _timestamp(information_cutoff_at, "information_cutoff_at").astimezone(MARKET_TIMEZONE).date()
    dates = _expected_sessions(cutoff_date - timedelta(days=1), 64)
    return dates[0].isoformat() if len(dates) == 64 else None


def calculate_market_features(
    bars: list[dict], information_cutoff_at: str, *, feed: str, adjustment: str = "raw"
) -> dict:
    """Calculate five declared features, with nulls and reasons for coverage gaps.

    ``t`` must identify the bar's date in America/New_York. The caller must supply
    Alpaca 1Day bars for one symbol and one explicit ``sip`` or ``iex`` feed.
    OHLCV are required. Alpaca trade count ``n`` and VWAP ``vw`` are validated when
    present but are not used in these features. Feed/adjustment tags, if supplied
    per bar, must agree with the call. Untagged inputs cannot prove feed identity.

    Returns use 22/64 closes for 21/63 intervals. Volatility is the sample standard
    deviation of 63 daily log close ratios times sqrt(252). Drawdown is the most
    negative running-peak drawdown over 63 closes. Dollar volume is the mean of
    close times volume for 21 sessions, not actual traded notional or market cap.
    Any missing expected session makes the affected feature unavailable. No price
    or volume is forward-filled. Split-like adjacent close ratios <=0.5 or >=2
    invalidate affected price windows, without identifying their cause. Passing
    this screen is not corporate-action verification.
    """
    if feed not in {"sip", "iex"}:
        raise ValueError("feed must be explicitly sip or iex; feeds cannot be blended")
    if adjustment != "raw":
        raise ValueError("only raw adjustment is supported")
    if not isinstance(bars, list):
        raise ValueError("bars must be a list of daily bar dictionaries")
    cutoff = _timestamp(information_cutoff_at, "information_cutoff_at")
    cutoff_local_date = cutoff.astimezone(MARKET_TIMEZONE).date()
    normalized, seen_dates = [], set()
    for position, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bar {position} must be a dictionary")
        if any(key not in bar for key in ("t", "o", "h", "l", "c", "v")):
            raise ValueError(f"bar {position} is missing a required t/OHLCV field")
        if bar.get("feed", feed) != feed or bar.get("adjustment", adjustment) != adjustment:
            raise ValueError("bar feed/adjustment differs from the declared source")
        timestamp = _timestamp(bar["t"], f"bar {position} t")
        day = timestamp.astimezone(MARKET_TIMEZONE).date()
        if day in seen_dates:
            raise ValueError(f"duplicate daily bar for New York date {day}")
        seen_dates.add(day)
        row = {key: _number(bar[key], key, positive=True) for key in ("o", "h", "l", "c")}
        row["v"] = _number(bar["v"], "v")
        if not row["l"] <= min(row["o"], row["c"]) <= max(row["o"], row["c"]) <= row["h"]:
            raise ValueError(f"impossible OHLC range for {day}")
        if not math.isfinite(row["c"] * row["v"]):
            raise ValueError(f"non-finite dollar-volume proxy for {day}")
        if bar.get("n") is not None:
            count = _number(bar["n"], "n")
            if not count.is_integer():
                raise ValueError("n must be a nonnegative integer")
            row["n"] = int(count)
        if bar.get("vw") is not None:
            row["vw"] = _number(bar["vw"], "vw", positive=True)
        if CALENDAR_START <= day <= CALENDAR_END and not _session(day):
            raise ValueError(f"daily bar on a non-session date under the calendar policy: {day}")
        row.update(t=timestamp.isoformat(), session_date=day.isoformat())
        normalized.append(row)

    normalized.sort(key=lambda row: row["session_date"])
    completed = [row for row in normalized if _available_at(date.fromisoformat(row["session_date"])) <= cutoff]
    by_date = {date.fromisoformat(row["session_date"]): row for row in completed}
    expected = _expected_sessions(cutoff_local_date - timedelta(days=1), 64)
    latest_expected = expected[-1] if expected else None
    latest = date.fromisoformat(completed[-1]["session_date"]) if completed else None
    earliest = date.fromisoformat(completed[0]["session_date"]) if completed else None
    stale = bool(latest_expected is not None and latest is not None and latest < latest_expected)
    features = dict.fromkeys(FEATURE_UNITS)
    history, flags = {}, set()
    if not completed:
        flags.add("no_completed_bars")
    if stale:
        flags.add("stale_last_completed_bar")
    for name, required in _REQUIRED_BARS.items():
        dates = expected[-required:]
        missing = [day for day in dates if day not in by_date]
        gaps = []
        if len(dates) < required:
            gaps.append("unsupported_calendar_scope")
        if earliest is None or any(day < earliest for day in missing):
            gaps.append("insufficient_history")
        if earliest is not None and any(day >= earliest for day in missing):
            gaps.append("missing_expected_sessions")
        if stale:
            gaps.append("stale_last_completed_bar")
        discontinuities = []
        if name != "mean_dollar_volume_21_sessions":
            for previous, current in zip(dates, dates[1:]):
                if previous not in by_date or current not in by_date:
                    continue
                ratio = by_date[current]["c"] / by_date[previous]["c"]
                if ratio <= 0.5 or ratio >= 2.0:
                    discontinuities.append({"previous_session_date": previous.isoformat(),
                                            "session_date": current.isoformat(),
                                            "close_ratio": ratio if math.isfinite(ratio) else None})
            if discontinuities:
                gaps.append("corporate_action_discontinuity")
        if not gaps:
            closes = [by_date[day]["c"] for day in dates]
            if "_return_" in name:
                value = closes[-1] / closes[0] - 1.0
            elif "_volatility_" in name:
                daily = [math.log(current / previous) for previous, current in zip(closes, closes[1:])]
                value = statistics.stdev(daily) * math.sqrt(252)
            elif "_drawdown_" in name:
                peak, value = closes[0], 0.0
                for close in closes:
                    peak = max(peak, close)
                    value = min(value, close / peak - 1.0)
            else:
                # Dividing first also avoids overflowing a finite notional sum.
                value = math.fsum((by_date[day]["c"] * by_date[day]["v"]) / required for day in dates)
            if not math.isfinite(value):
                raise ValueError(f"non-finite calculated feature: {name}")
            features[name] = value
        history[name] = {"required_bars": required, "observed_bars": len(dates) - len(missing),
                         "window_start_date": dates[0].isoformat() if dates else None,
                         "window_end_date": dates[-1].isoformat() if dates else None,
                         "missing_session_dates": [day.isoformat() for day in missing],
                         "discontinuities": discontinuities, "gaps": gaps}
        flags.update(gaps)

    completed_hash = hashlib.sha256(json.dumps(completed, sort_keys=True, separators=(",", ":"),
                                               allow_nan=False).encode()).hexdigest()
    return {"schema_version": "historical-raw-market-features-v1", "features": features,
            "units": dict(FEATURE_UNITS), "feature_history": history,
            "quality_flags": sorted(flags), "all_features_available": all(value is not None for value in features.values()),
            "feed": feed, "adjustment": adjustment, "price_basis": "unadjusted",
            "corporate_actions_verified": False,
            "provenance": {"information_cutoff_at": cutoff.isoformat(), "market_timezone": "America/New_York",
                           "timeframe": "1Day", "input_bar_count": len(bars),
                           "completed_bar_count": len(completed),
                           "excluded_incomplete_or_future_bar_count": len(bars) - len(completed),
                           "last_completed_bar_at": completed[-1]["t"] if completed else None,
                           "last_completed_session_date": latest.isoformat() if latest else None,
                           "last_completed_bar_available_at": _available_at(latest).isoformat() if latest else None,
                           "latest_expected_completed_session_date": latest_expected.isoformat() if latest_expected else None,
                           "last_completed_bar_age_calendar_days": (cutoff_local_date - latest).days if latest else None,
                           "normalized_completed_bars_sha256": completed_hash,
                           "availability_basis": "conservative_next_New_York_midnight_policy",
                           "historical_publication_proof": False, "feed_identity_verified": False,
                           "calendar_policy": CALENDAR_POLICY_VERSION,
                           "calendar_supported_session_dates": [CALENDAR_START.isoformat(), CALENDAR_END.isoformat()],
                           "calendar_is_listing_or_provider_status_proof": False},
            "limitations": ["Feed is caller-declared. IEX coverage and volume are not consolidated SIP coverage; no feed blending is performed.",
                            "Raw prices are not adjusted for splits or dividends. The discontinuity screen does not verify corporate actions or total returns.",
                            "The dollar-volume feature is close times reported volume, not actual traded notional or market capitalization.",
                            "Calendar policy covers full-day US equity closures in 2016–2026; it cannot prove issuer listing, halt status or provider completeness.",
                            "Current retrieval clocks do not establish historical publication or original-version availability of provider bars.",
                            "Missing bars and feature gaps do not establish acquisition outcomes or change model/label admission."]}
