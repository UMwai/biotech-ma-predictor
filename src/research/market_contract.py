"""Feature source parity shared by market assembly, fitting and application."""
from src.research.market_features import CALENDAR_POLICY_VERSION, FEATURE_UNITS


def market_feature_contract(feed: str) -> dict:
    if feed not in {'sip', 'iex'}:
        raise ValueError('market feature contract requires SIP or IEX')
    return {'schema_version': 'alpaca-daily-market-feature-contract-v1',
            'provider': 'Alpaca', 'feed': feed, 'adjustment': 'raw',
            'timeframe': '1Day', 'currency': 'USD',
            'calculation_schema': 'historical-raw-market-features-v1',
            'calendar_policy': CALENDAR_POLICY_VERSION,
            'availability_policy': 'next_new_york_midnight',
            'corporate_actions_verified': False,
            'original_vendor_vintage_archived': False}


def validate_market_feature_contract(value: dict, names: list[str]) -> None:
    has_market = bool(set(names) & set(FEATURE_UNITS))
    supplied = value.get('market_data_contract')
    if has_market:
        if not isinstance(supplied, dict) or supplied != market_feature_contract(supplied.get('feed')):
            raise ValueError('market features require their exact source/feed/derivation contract')
        if any(value.get('feature_units', {}).get(name) != FEATURE_UNITS[name]
               for name in set(names) & set(FEATURE_UNITS)):
            raise ValueError('market feature units differ from the declared calculation contract')
    elif supplied is not None:
        raise ValueError('market feature contract supplied without market features')
