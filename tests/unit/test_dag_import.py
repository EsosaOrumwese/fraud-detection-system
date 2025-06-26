# import os
# import sys
#
# # ── BEGIN PATCH ──
# # Airflow 3 calls os.register_at_fork() on import; Windows os module doesn't have it.
# # Monkey-patch it here, in this file only, before importing anything in Airflow.
# if sys.platform.startswith("win") and not hasattr(os, "register_at_fork"):
#     os.register_at_fork = lambda *args, **kwargs: None  # type: ignore
# # ── END PATCH ──
#
# from airflow.models.dagbag import DagBag  # correct import for Airflow 3
#
#
# def test_import_dags():
#     """
#     Ensure all DAGs in orchestration/airflow/dags can be parsed without import errors.
#     """
#     dagbag = DagBag(
#         dag_folder="orchestration/airflow/dags",
#         include_examples=False,
#     )
#     errors = dagbag.import_errors
#     assert not errors, f"DAG import failures: {errors}"
