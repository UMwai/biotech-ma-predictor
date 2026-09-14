"""Portable models retain feed, price and calculation parity at application."""
import copy
from datetime import timedelta

import pytest

from src.research.market_contract import market_feature_contract
from src.research.market_features import FEATURE_UNITS
from src.research.training import TrainingBlocked, TrainingConfig, apply_baseline, train_baseline, validate_training_data
from test_training import NOW, requires_model, synthetic_dataset


def dataset():
    data = synthetic_dataset()
    data['feature_names'] += list(FEATURE_UNITS)
    data['feature_units'].update(FEATURE_UNITS)
    data['market_data_contract'] = market_feature_contract('sip')
    for row in data['observations']:
        row['features'].update({name: None for name in FEATURE_UNITS})
    return data


@pytest.mark.parametrize('change', ['missing', 'adjustment', 'vintage', 'derivation', 'feed', 'units'])
def test_unsupported_market_semantics_block_before_fitting(change):
    data = dataset()
    if change == 'missing': data.pop('market_data_contract')
    elif change == 'adjustment': data['market_data_contract']['adjustment'] = 'all'
    elif change == 'vintage': data['market_data_contract']['original_vendor_vintage_archived'] = True
    elif change == 'derivation': data['market_data_contract']['calculation_schema'] = 'different-formula'
    elif change == 'feed': data['market_data_contract']['feed'] = 'mixed'
    else: data['feature_units']['raw_price_return_21_sessions'] = 'percent'
    with pytest.raises(TrainingBlocked): validate_training_data(data, now=NOW)


@requires_model
def test_fitted_market_models_bind_source_contract_and_reject_other_feed():
    data = dataset()
    run = train_baseline(data, TrainingConfig(2021), now=NOW)
    model = run['final_model']
    assert model['market_data_contract'] == market_feature_contract('sip')
    assert all(f['model']['market_data_contract'] == model['market_data_contract'] for f in run['folds'])
    row = copy.deepcopy(data['observations'][0])
    row.update(observation_at=(NOW+timedelta(days=2)).isoformat(),
               information_cutoff_at=(NOW+timedelta(days=1)).isoformat(),
               feature_max_available_at=(NOW+timedelta(days=1)).isoformat())
    current = {'schema_version': 'current-company-features-v1', 'feature_names': data['feature_names'],
               'feature_units': data['feature_units'], 'market_data_contract': market_feature_contract('sip'),
               'observations': [row]}
    assert apply_baseline(model, current, now=NOW+timedelta(days=3))['observations'][0]['probability'] is None
    current['market_data_contract'] = market_feature_contract('iex')
    with pytest.raises(TrainingBlocked, match='differs from fitted model'):
        apply_baseline(model, current, now=NOW+timedelta(days=3))
