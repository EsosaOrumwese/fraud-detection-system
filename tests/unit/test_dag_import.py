import pytest
from airflow.models.dagbag import DagBag  # correct import for Airflow 3


def test_import_dags():
    """
    Ensure all DAGs in orchestration/airflow/dags can be parsed
    without import errors.
    """
    dagbag = DagBag(
        dag_folder="orchestration/airflow/dags",
        include_examples=False,
    )
    errors = dagbag.import_errors
    assert not errors, f"DAG import failures: {errors}"
