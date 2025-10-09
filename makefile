.PHONY: run-s0 run-s0-no-validate

run-s0:
	python scripts/run_s0_from_config.py --config configs/runs/s0_synthetic_config.json

run-s0-no-validate:
	python scripts/run_s0_from_config.py --config configs/runs/s0_synthetic_config.json --no-validate
