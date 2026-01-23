from fraud_detection.scenario_runner.ids import run_id_from_equivalence_key, scenario_set_to_id


def test_run_id_is_deterministic() -> None:
    key = "example-key"
    assert run_id_from_equivalence_key(key) == run_id_from_equivalence_key(key)


def test_scenario_set_is_order_independent() -> None:
    first = scenario_set_to_id(["baseline", "stress"])
    second = scenario_set_to_id(["stress", "baseline", "baseline"])
    assert first == second
