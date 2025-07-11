import pytest
from datetime import date
from pydantic import ValidationError

from fraud_detection.simulator.config import TemporalConfig, TimeComponentConfig  # type: ignore

def test_defaults_do_not_error_and_have_expected_values():
    cfg = TemporalConfig(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31)
    )
    # Defaults
    assert cfg.weekday_weights is None
    assert cfg.time_components is None
    assert cfg.distribution_type == "gaussian"
    assert cfg.chunk_size is None

def test_valid_weekday_weights_and_time_components_are_normalized():
    # supply unnormalized weights and time components
    raw_ww = {0: 2.0, 1: 1.0, 6: 1.0}  # sum=4.0
    raw_tcs = [
        {"mean_hour": 8.0, "std_hours": 1.0, "weight": 2.0},
        {"mean_hour": 20.0, "std_hours": 2.0, "weight": 1.0},
    ]  # sum=3.0

    cfg = TemporalConfig(
        start_date=date(2025, 5, 1),
        end_date=date(2025, 5, 31),
        weekday_weights=raw_ww,
        time_components=[TimeComponentConfig(**tc) for tc in raw_tcs],
        chunk_size=1,
    )

    # weekday_weights normalized to sum=1
    normalized_ww = cfg.weekday_weights
    assert pytest.approx(sum(normalized_ww.values()), rel=1e-6) == 1.0
    assert normalized_ww[0] == pytest.approx(2.0 / 4.0)
    assert normalized_ww[1] == pytest.approx(1.0 / 4.0)
    assert normalized_ww[6] == pytest.approx(1.0 / 4.0)

    # time_components weights normalized to sum=1
    tcs = cfg.time_components
    total_w = sum(tc.weight for tc in tcs)
    assert pytest.approx(total_w, rel=1e-6) == 1.0
    # check individual normalization
    assert tcs[0].weight == pytest.approx(2.0 / 3.0)
    assert tcs[1].weight == pytest.approx(1.0 / 3.0)

    # chunk_size=1 is allowed
    assert cfg.chunk_size == 1

def test_invalid_weekday_key_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            weekday_weights={7: 1.0}
        )

def test_negative_weekday_weight_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            weekday_weights={0: -0.5, 1: 0.5}
        )

def test_zero_sum_weekday_weights_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            weekday_weights={0: 0.0, 1: 0.0}
        )

def test_time_components_zero_total_weight_raises():
    zero_tcs = [
        {"mean_hour": 9.0, "std_hours": 1.0, "weight": 0.0},
        {"mean_hour": 15.0, "std_hours": 2.0, "weight": 0.0},
    ]
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 28),
            time_components=[TimeComponentConfig(**tc) for tc in zero_tcs]
        )

def test_chunk_size_zero_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
            chunk_size=0
        )

def test_end_before_start_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 5, 2),
            end_date=date(2025, 5, 1),
        )

def test_invalid_distribution_type_raises():
    with pytest.raises(ValidationError):
        TemporalConfig(
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            distribution_type="uniform"
        )

# Boundary checks for TimeComponentConfig
@pytest.mark.parametrize("kwargs", [
    {"mean_hour": 24.0, "std_hours": 1.0, "weight": 1.0},
    {"mean_hour": -1.0, "std_hours": 1.0, "weight": 1.0},
])
def test_time_component_mean_hour_bounds_raise(kwargs):
    with pytest.raises(ValidationError):
        TimeComponentConfig(**kwargs)

@pytest.mark.parametrize("kwargs", [
    {"mean_hour": 10.0, "std_hours": 0.0, "weight": 1.0},
    {"mean_hour": 10.0, "std_hours": -1.0, "weight": 1.0},
])
def test_time_component_std_hours_bounds_raise(kwargs):
    with pytest.raises(ValidationError):
        TimeComponentConfig(**kwargs)

def test_time_component_negative_weight_raises():
    with pytest.raises(ValidationError):
        TimeComponentConfig(mean_hour=10.0, std_hours=1.0, weight=-0.1)

# chunk_size positive boundary
def test_chunk_size_positive_allows():
    cfg = TemporalConfig(
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 30),
        chunk_size=10,
    )
    assert cfg.chunk_size == 10

# YAML string keys coercion for weekday_weights
def test_string_key_weekday_weights_coerced():
    cfg = TemporalConfig(
        start_date=date(2025, 7, 1),
        end_date=date(2025, 7, 2),
        weekday_weights={"0": 2, "1": 2},
    )
    # ensure keys are ints after validation
    assert 0 in cfg.weekday_weights
    assert 1 in cfg.weekday_weights