from fraud_detection.scenario_runner.catalogue import OutputCatalogue


def test_catalogue_strips_path_template(tmp_path):
    payload = """
outputs:
  - output_id: sample_output
    path_template: "data/path/part-*.parquet\\n"
    partitions: []
    scope: scope_global
    read_requires_gates: []
    availability: required
"""
    path = tmp_path / "catalogue.yaml"
    path.write_text(payload, encoding="utf-8")
    catalogue = OutputCatalogue(path)
    entry = catalogue.get("sample_output")
    assert entry.path_template == "data/path/part-*.parquet"
