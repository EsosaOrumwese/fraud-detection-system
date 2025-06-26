Below is a thorough, step‐by‐step walkthrough of the entire `train_baseline.py` file. I’ll assume you’re familiar with Python, Pandas dataframes, and NumPy arrays, and I’ll explain every new concept (like Polars, scikit-learn pipelines, XGBoost, and MLflow) as we go. The goal is for you to understand precisely what each line and section does, so you can read, modify, or extend it with confidence.

---

## 1. File header, imports, and setup

```python
"""
train_baseline.py
─────────────────

Baseline fraud classifier: XGBoost + sklearn ColumnTransformer.

Usage (as a CLI):
    poetry run python -m fraud_detection.modelling.train_baseline \
        --rows 500000 \
        --parquet outputs/payments_1000000_1_000_000.parquet \
        --n-est 300 \
        --max-depth 6 \
        --learning-rate 0.1 \
        --max-categories 100 \
        --seed 42

This module is organized so that:
  - Helper functions (data loading, pipeline building, MLflow setup) are
    type-annotated, fully documented, and raise descriptive exceptions.
  - The `main()` function handles CLI parsing, MLflow context, and high-level logging.
  - Errors at any step are caught and logged before propagating.
"""
```

1. **Triple-quoted string at the very top**:

   * In Python, any string literal that appears as the *first* statement in a module (file), class, or function becomes that module’s “docstring.”
   * Here, this docstring explains at a glance:

     * What `train_baseline.py` is (it’s our “baseline fraud classifier”).
     * How to run it from the command line (the example `poetry run python -m …` shows the typical flags).
     * Its organization: we have helper functions, and a `main()` that orchestrates everything.

   If you ever run

   ```bash
   python -c "import fraud_detection.modelling.train_baseline as m; print(m.__doc__)"
   ```

   you’d see exactly this text.

---

### 1.1. Future import, standard libraries, and type hints

```python
from __future__ import annotations

import argparse
import datetime
import logging
import os
import pathlib
import sys
import yaml
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
import polars as pl
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier
```

Let’s break this down line by line:

1. **`from __future__ import annotations`**

   * Starting in Python 3.7, you can put this at the top. It tells Python to store function and variable type hints (the things inside `->` or inside `: type`) as **strings** internally, rather than trying to evaluate them right away. This avoids certain circular‐import issues.
   * In practice here, it just means that when you write a function signature like:

     ```python
     def foo(x: pathlib.Path) -> dict[str, Any]:
         ...
     ```

     Python will not immediately try to evaluate `dict[str, Any]` at runtime, but keep it as a string and resolve it later if needed.

2. **`import argparse`**

   * The standard library module used to parse command‐line arguments (`--rows`, `--parquet`, etc.).
   * We’ll see later how we define `parser = argparse.ArgumentParser(...)` and then `parser.parse_args()` to get those flags.

3. **`import datetime`**

   * The standard library’s `datetime` module. We’ll use `datetime.datetime.utcnow()` to tag our MLflow run with a timestamp.

4. **`import logging`**

   * The standard logging module. It provides a way to emit log messages (INFO, WARNING, ERROR) that are better than simple `print(...)` statements. We’ll set up a logger so that everything printed has a consistent timestamp and severity level.

5. **`import os`**

   * The standard library’s OS module. We only use it once (to read `os.getenv("GIT_SHA", "local")`), which fetches an environment variable (we’ll tag our run with the current Git SHA if it exists).

6. **`import pathlib`**

   * A modern, object‐oriented way to manipulate filesystem paths (`Path` objects instead of raw strings). For example, `pathlib.Path("config/transaction_schema.yaml")` is a path object that we can check for existence, read from, join with other parts, etc.

7. **`import sys`**

   * We’ll use `sys.exit(1)` if anything goes wrong in `main()`, so the script exits with a nonzero code in case of failure.

8. **`import yaml`**

   * We rely on PyYAML to parse our schema file (`transaction_schema.yaml`). That schema is a YAML file defined under `config/`, and we need to read it in so we know which columns exist, their data types, and so on.

9. **`from typing import Any`**

   * A very general type hint. We’ll see a function `load_schema(...) -> dict[str, Any]` which means “a dictionary whose keys are strings and whose values can be *anything*.” When you see `Any`, it simply means “I’m not constraining this further.”

10. **`import mlflow` and `import mlflow.sklearn`**

    * MLflow is the library we use for experiment tracking.
    * `mlflow` is the core; `mlflow.sklearn` has helper functions for logging sklearn pipeline artifacts (the whole `Pipeline` object).

11. **`import pandas as pd`**

    * You already know Pandas. We’ll use it after sampling from Polars to manipulate data in memory, to split into features/labels, and so forth.

12. **`import polars as pl`**

    * Polars is a DataFrame library (similar idea to Pandas) but often faster and uses lazy execution. Here, we use it in “lazy” mode (`pl.scan_parquet(...)`) to count rows and sample quickly, then call `.collect()` to turn it into an in‐memory DataFrame, and finally convert to a Pandas DataFrame.
    * This is a common pattern: use Polars to read big Parquet files and sample, then switch to Pandas once we have a small subset.

13. **`from sklearn.compose import ColumnTransformer`**

    * In scikit-learn, a `ColumnTransformer` lets you apply different preprocessing steps to different subsets of columns. For instance, you might one‐hot-encode all categorical columns, but “passthrough” numeric columns (i.e. leave them as‐is). The result is a single transformer object that scikit-learn knows how to apply.

14. **`from sklearn.metrics import average_precision_score`**

    * A function to compute the “average precision” (AUC-PR) metric. It’s the area under the precision‐recall curve. Because fraud is very rare (\~0.3 %), AUC-PR is a more meaningful metric than AUC-ROC. We’ll use this to quantify how well the model is separating fraud vs. non‐fraud.

15. **`from sklearn.model_selection import train_test_split`**

    * The standard scikit-learn function to split data into training and test sets. We will do an **80/20 stratified split**, meaning:

      * 80 % of the sampled rows go to training, 20 % to testing.
      * “Stratified” means we preserve the same proportion of positive (fraud) vs. negative (nonfraud) in both sets.

16. **`from sklearn.pipeline import Pipeline`**

    * A `Pipeline` is an object that chains multiple steps—e.g., first we transform columns (one‐hot encode), then we fit the XGBoost model. Instead of writing “transform, then fit, then predict” manually, a Pipeline bundles them. At inference time, you call `pipeline.predict_proba(...)`, and it will do every step in order (first apply the encoder to raw columns, then run the model).

17. **`from sklearn.preprocessing import OneHotEncoder`**

    * A scikit-learn transformer that takes categorical columns and turns each unique category into a new column of 0/1 (one‐hot encoding). For example: if a column “merchant\_category” has values {“food”, “travel”, “electronics”}, one‐hot would create three new columns called `merchant_category_food`, `merchant_category_travel`, `merchant_category_electronics`, with a 1 in exactly one of them per row.

18. **`from xgboost import XGBClassifier`**

    * The XGBoost classifier object. XGBoost is a high-performance gradient boosting library; `XGBClassifier` is its scikit-learn‐compatible wrapper. You pass hyperparameters like `n_estimators`, `max_depth`, `learning_rate`, etc., then call `.fit(X_train, y_train)` just like a scikit-learn model.

---

At this point, all the external libraries are available. Next, we configure our own global constants and helper functions.

---

## 2. Logger setup and base directory

```python
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

BASE_DIR = pathlib.Path(__file__).parent.parent.parent  # Points to project root
SCHEMA_PATH = BASE_DIR / "schema" / "transaction_schema.yaml"
```

1. **`logger = logging.getLogger(__name__)`**

   * Creates a “logger” object whose name is the module’s name (i.e. `"fraud_detection.modelling.train_baseline"`). This is standard practice: each module gets its own logger.
   * You’ll later call `logger.info(...)` or `logger.exception(...)` and the messages will be prefixed with a timestamp, level, and module name, as specified below.

2. **`logging.basicConfig(...)`**

   * Configures the root logger so that any logging call at INFO level or higher will print to standard output with a uniform format.
   * `level=logging.INFO` means “only show messages at INFO, WARNING, ERROR, or CRITICAL (i.e. skip DEBUG).”
   * `format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"` means each log line will look like:

     ```
     2025-06-05 12:41:00 [INFO] fraud_detection.modelling.train_baseline - Loaded 500000 rows from payments_1000000_1_000_000.parquet
     ```
   * `datefmt="%Y-%m-%d %H:%M:%S"` chooses the timestamp format.

3. **`BASE_DIR = pathlib.Path(__file__).parent.parent.parent`**

   * `__file__` is the filepath of the current script (e.g. `/home/user/repo/src/fraud_detection/modelling/train_baseline.py`).
   * `.parent` once would be `/home/user/repo/src/fraud_detection/modelling/`.
   * `.parent.parent` moves up to `/home/user/repo/src/fraud_detection/`.
   * `.parent.parent.parent` moves up to the project root, `/home/user/repo/`.
   * By computing `BASE_DIR` at import time, the code no longer assumes “I’m running from the repo root.” Instead, it will *always* know where “config/transaction\_schema.yaml” lives relative to itself.

4. **`SCHEMA_PATH = BASE_DIR / "config" / "transaction_schema.yaml"`**

   * This builds a `pathlib.Path` object pointing at the file `config/transaction_schema.yaml` under the project root.
   * Later, instead of hardcoding `"config/transaction_schema.yaml"`, we’ll always refer to `SCHEMA_PATH`.

---

## 3. Loading and validating the schema

```python
def load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
    """Read and parse the transaction_schema.yaml file. Raise if missing/invalid."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found at {schema_path.resolve()}")
    try:
        content = schema_path.read_text()
        schema = yaml.safe_load(content)
        if not isinstance(schema, dict) or "fields" not in schema:
            raise ValueError("Schema YAML does not contain top-level 'fields'.")
        return schema
    except yaml.YAMLError as e:
        raise RuntimeError(f"Unable to parse YAML schema file: {e}") from e

SCHEMA = load_schema(SCHEMA_PATH)
TARGET = "label_fraud"
# Identify which columns are categorical vs. numeric
CATEGORICAL: list[str] = [
    f["name"]
    for f in SCHEMA["fields"]
    if f.get("dtype") in ("enum", "string") and f["name"] != TARGET
]
NUMERIC: list[str] = [
    f["name"]
    for f in SCHEMA["fields"]
    if f.get("dtype") in ("int", "float", "datetime")
]
```

### 3.1. `load_schema(...)` function

* **Signature**:

  ```python
  def load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
  ```

  * We expect `schema_path` to be a `pathlib.Path` object.
  * We promise to return a dictionary (`dict[str, Any]`) if everything goes well. The structure of this dictionary comes from the YAML file, which should look something like:

    ```yaml
    version: "0.1.0"
    fields:
      - name: transaction_id
        dtype: string
      - name: amount
        dtype: float
      - name: label_fraud
        dtype: int
      # … etc., up to 24 fields total …
    ```

1. **`if not schema_path.exists(): raise FileNotFoundError(...)`**

   * Checks if the `transaction_schema.yaml` file actually exists on disk. If it doesn’t, we raise a `FileNotFoundError`, including the absolute path (`schema_path.resolve()`) to help the user locate the missing file.

2. **`content = schema_path.read_text()`**

   * Reads the entire YAML file into a Python string. Equivalent to:

     ```python
     with open(schema_path, "r") as f:
         content = f.read()
     ```
   * `content` is now a string containing the YAML.

3. **`schema = yaml.safe_load(content)`**

   * `yaml.safe_load` parses the YAML string into a Python object—usually a nested combination of dictionaries and lists. In our case, we expect `schema` to be something like:

     ```python
     {
       "version": "0.1.0",
       "fields": [
         {"name": "transaction_id", "dtype": "string"},
         {"name": "amount", "dtype": "float"},
         {"name": "label_fraud", "dtype": "int"},
         # … 21 more …
       ],
     }
     ```

4. **`if not isinstance(schema, dict) or "fields" not in schema:`**

   * Just a sanity check: if for some reason the YAML did not parse into a dictionary, or if it did but has no `"fields"` key, then something’s wrong. We raise a `ValueError` with a helpful message.

5. **`except yaml.YAMLError as e:`**

   * If `safe_load()` fails because the YAML is malformed, it will throw a `yaml.YAMLError`. We catch it and re‐raise a `RuntimeError` with an explanatory message. The `from e` keeps the original traceback.

6. **`return schema`**

   * If everything goes well, we hand back the parsed dictionary.
   * Immediately after the function definition, we call:

     ```python
     SCHEMA = load_schema(SCHEMA_PATH)
     ```

     so `SCHEMA` is a global variable containing the entire schema.

### 3.2. Defining `TARGET`, `CATEGORICAL`, and `NUMERIC`

```python
TARGET = "label_fraud"
```

* We hardcode that the column named `"label_fraud"` is our target (the binary 0/1 column for fraud vs. non‐fraud).
* Note: we assume that in the YAML, one of the 24 fields is indeed `name: label_fraud` with `dtype: int`.

```python
CATEGORICAL: list[str] = [
    f["name"]
    for f in SCHEMA["fields"]
    if f.get("dtype") in ("enum", "string") and f["name"] != TARGET
]
```

* We build a list of **all column names** whose `dtype` is `"enum"` or `"string"`, and which are not our target.
* For example, if the schema has a field:

  ```yaml
  - name: merchant_category
    dtype: enum
  ```

  then `"merchant_category"` ends up in this list.
* We exclude the `TARGET` column, even if it is typed as `"int"`—but since `label_fraud` has dtype `"int"`, it wouldn’t have made it into this list anyway. We do the extra check (`and f["name"] != TARGET`) just in case someone (wrongly) typed `label_fraud` as `"string"` in the YAML.

```python
NUMERIC: list[str] = [
    f["name"]
    for f in SCHEMA["fields"]
    if f.get("dtype") in ("int", "float", "datetime")
]
```

* Similarly, we build a list of all columns whose dtype is `"int"`, `"float"`, or `"datetime"`. Those are “numeric” for our purposes.
* Example: if the schema has:

  ```yaml
  - name: amount
    dtype: float
  ```

  it ends up in `NUMERIC`.
* Notice we do not explicitly exclude `label_fraud` here; that means `label_fraud` will also be included in `NUMERIC` because it has dtype `"int"`. That’s okay, because later when we actually split features vs. target, we do `df.drop(columns=[TARGET])` to remove it from X.

---

## 4. Data loading and preprocessing helpers

Next, we have two helper functions: `load_data(...)` and `calc_class_weight(...)`, plus the core `build_pipeline(...)`.

### 4.1. `load_data(...)`

```python
def load_data(
    rows: int,
    parquet_path: pathlib.Path,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Load up to `rows` records from the given Parquet file, sampled without replacement.

    Args:
        rows: Number of rows to sample. Must be <= total rows in file.
        parquet_path: Path to a single Parquet file conforming to SCHEMA.
        seed: Random seed for reproducibility.

    Returns:
        A pandas.DataFrame of shape (rows, n_columns) where n_columns == len(SCHEMA["fields"]).
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found at {parquet_path.resolve()}")
    # Count total rows in Parquet
    total_rows_df = pl.scan_parquet(parquet_path).select(pl.count()).collect()
    total_rows = int(total_rows_df["count"][0])
    if rows > total_rows:
        raise ValueError(f"Requested {rows} rows but file has only {total_rows} rows.")

    # Sample without replacement (deterministic)
    df_polars = (
        pl.scan_parquet(parquet_path)
        .sample(n=rows, seed=seed, with_replacement=False)
        .collect()
    )
    df = df_polars.to_pandas()
    logger.info("Loaded %d rows from %s", rows, parquet_path.name)
    return df
```

Let’s unpack each part:

1. **Signature**:

   * `rows: int` means “how many rows to sample from the Parquet file.”
   * `parquet_path: pathlib.Path` is where the Parquet file lives (e.g. `outputs/payments_1000000_1_000_000.parquet`).
   * `seed: int = 42` is our random seed for reproducibility—so when we call `.sample(...)`, we always get the same selection if the seed is the same.
   * We promise to return a `pd.DataFrame` (a Pandas DataFrame).

2. **Check existence**:

   ```python
   if not parquet_path.exists():
       raise FileNotFoundError(f"Parquet file not found at {parquet_path.resolve()}")
   ```

   * If the file does not exist, immediately throw an error explaining which path was missing.

3. **Count total rows using Polars**:

   ```python
   total_rows_df = pl.scan_parquet(parquet_path).select(pl.count()).collect()
   total_rows = int(total_rows_df["count"][0])
   ```

   * `pl.scan_parquet(parquet_path)` opens the Parquet file in **lazy** mode (it does not load all data into memory yet).
   * `.select(pl.count())` tells Polars: “I only care about the total row count, not all columns.” Polars can optimize this behind the scenes (it knows Parquet stores row‐counts in metadata).
   * `.collect()` executes the lazy query and returns an in-memory Polars DataFrame with a single column called `"count"`, whose value is the number of rows.
   * `total_rows_df["count"][0]` extracts that integer.
   * Converting to `int(...)` ensures we have a plain Python integer.

4. **Ensure `rows <= total_rows`**:

   ```python
   if rows > total_rows:
       raise ValueError(f"Requested {rows} rows but file has only {total_rows} rows.")
   ```

   * If someone asked for more rows than exist, we bail out with a clear error message. This avoids letting `.sample(n=rows)` blow up in a more confusing way.

5. **Sample exactly `rows` rows without replacement**:

   ```python
   df_polars = (
       pl.scan_parquet(parquet_path)
       .sample(n=rows, seed=seed, with_replacement=False)
       .collect()
   )
   ```

   * We do `pl.scan_parquet(parquet_path)` again (lazy).
   * Then `.sample(n=rows, seed=seed, with_replacement=False)` instructs Polars:

     * “Randomly pick exactly `rows` rows from the entire dataset,”
     * “Don’t sample the same row multiple times (`with_replacement=False`).”
     * “Use this particular `seed` so you get the same sample each time.”
   * `.collect()` executes the query, returning a Polars DataFrame in memory with exactly `rows` rows.

6. **Convert to a Pandas DataFrame**:

   ```python
   df = df_polars.to_pandas()
   ```

   * We call `.to_pandas()` on the Polars DataFrame. Now we have a `pd.DataFrame`, which plays nicely with scikit-learn and our existing code.
   * If you print `df.head()`, you’d see the first few rows of sampled transactions.

7. **Log the fact that we loaded data**:

   ```python
   logger.info("Loaded %d rows from %s", rows, parquet_path.name)
   ```

   * Emits an INFO‐level log message:

     ```
     2025-06-05 12:35:02 [INFO] fraud_detection.modelling.train_baseline - Loaded 500000 rows from payments_1000000_1_000_000.parquet
     ```
   * Using `parquet_path.name` only prints the filename (not the entire path).

8. **Return the Pandas DataFrame**:

   ```python
   return df
   ```

At this point, calling `df = load_data(200, Path("outputs/payments_…parquet"))` will give you a Pandas DataFrame with exactly 200 randomly selected rows.

---

### 4.2. `calc_class_weight(...)`

```python
def calc_class_weight(y: pd.Series) -> float:
    """
    Compute `scale_pos_weight = negative_count / positive_count` for XGBoost.

    Args:
        y: pd.Series of binary labels (0/1), where 1 indicates fraud.

    Returns:
        A float to assign to `scale_pos_weight`.
    """
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0:
        raise ValueError("No positive examples in training set; cannot compute scale_pos_weight.")
    return neg / pos
```

1. **Signature**:

   * `y: pd.Series` means `y` is a Pandas Series (one‐dimensional array) of labels 0 or 1.
   * We return a `float`.

2. **Count positives**:

   ```python
   pos = int(y.sum())
   ```

   * If `y` is a series like `[0, 1, 0, 0, 1, 0, 0, 0, 0, 1]`, then `y.sum()` = 3.0 (because there are 3 ones).
   * Converting to `int(...)` just makes it a Python integer `pos = 3`.

3. **Count negatives**:

   ```python
   neg = int(len(y) - pos)
   ```

   * `len(y)` is the total number of rows in `y`. If `len(y)` is 10 and `pos` = 3, then `neg` = 7.

4. **Check “zero positives”**:

   ```python
   if pos == 0:
       raise ValueError("No positive examples in training set; cannot compute scale_pos_weight.")
   ```

   * If you somehow called this on a dataset with zero fraud examples (all zeros), then `pos = 0`.
   * XGBoost’s `scale_pos_weight` is `negative_count / positive_count`, but dividing by zero is impossible. Instead of letting XGBoost crash, we proactively raise a clear error.

5. **Compute the ratio**:

   ```python
   return neg / pos
   ```

   * Example: if `pos = 3` and `neg = 997`, then `neg / pos` ≈ 997/3 ≈ 332.33.
   * In XGBoost, you would pass this as `scale_pos_weight=332.33`. That tells XGBoost “fraud is 332× rarer than non‐fraud, so weigh positive class 332× more heavily to counteract the imbalance.”

---

### 4.3. `build_pipeline(...)`

```python
def build_pipeline(
    max_categories: int,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    tree_method: str = "hist",
) -> Pipeline:
    """
    Construct a scikit-learn pipeline: OneHotEncoder → passthrough numerics → XGBoost.

    Args:
        max_categories: `max_categories` argument for OneHotEncoder (sklearn ≥1.4).
        n_estimators: Number of XGBoost trees.
        max_depth: Maximum depth per tree.
        learning_rate: XGBoost learning rate.
        tree_method: XGBoost `tree_method` (e.g. "hist" for fast CPU training).

    Returns:
        A sklearn Pipeline that accepts raw DataFrame (with SCHEMA columns) and yields a fitted XGBClassifier.
    """
    one_hot = OneHotEncoder(
        handle_unknown="ignore",
        sparse_output=True,
        max_categories=max_categories,
    )
    ct = ColumnTransformer(
        transformers=[
            ("cat", one_hot, CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ],
        remainder="drop",  # drop any unexpected columns
        sparse_threshold=0.0,  # ensure output is sparse if any transformer is sparse
    )
    model = XGBClassifier(
        tree_method=tree_method,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        objective="binary:logistic",
        eval_metric="aucpr",
        use_label_encoder=False,
        verbosity=0,
    )
    pipeline = Pipeline(steps=[("prep", ct), ("clf", model)])
    return pipeline
```

This function builds a **scikit‐learn pipeline** consisting of:

1. **One‐hot encoding for categorical columns**,
2. **Passthrough of numeric columns**,
3. **An XGBoost classifier** at the end.

Let’s walk through each piece:

1. **Signature**:

   * We accept four hyperparameters from the command line:

     * `max_categories: int` → maximum cardinality for the OneHotEncoder. If any categorical column has more unique values than this, it will be truncated or raise an error internally; by default we use 100 in our CLI.
     * `n_estimators: int` → number of boosted trees in XGBoost.
     * `max_depth: int` → maximum depth of each tree.
     * `learning_rate: float` → shrinkage factor for XGBoost (smaller values make training slower but more precise).
   * `tree_method: str = "hist"` is optional (default is “hist”), the recommended CPU‐optimized tree construction algorithm that XGBoost provides.

2. **OneHotEncoder instantiation**:

   ```python
   one_hot = OneHotEncoder(
       handle_unknown="ignore",
       sparse_output=True,
       max_categories=max_categories,
   )
   ```

   * `OneHotEncoder` is a scikit-learn transformer. When you call `one_hot.fit_transform(X_categorical)`, it will:

     * Identify all unique categories in each column (unless they exceed `max_categories`, in which case it follows sklearn’s internal policy—often it groups rare categories into “others” or truncates).
     * Create a sparse matrix where each unique category becomes its own column (0/1).
   * `handle_unknown="ignore"` tells it: “If at inference time you see a category the encoder never saw during `.fit()`, just encode it as all zeros (rather than crashing).”
   * `sparse_output=True` means the output of `fit_transform(...)` will be a sparse CSR matrix, not a dense NumPy array. When you have many categories, sparse matrices save memory.
   * `max_categories=max_categories` enforces that any column in CATEGORICAL has at most `max_categories` distinct values. If a column has more, you might get an error or a truncated set. This helps guarantee we won’t blow past our 2 GB memory limit.

3. **ColumnTransformer instantiation**:

   ```python
   ct = ColumnTransformer(
       transformers=[
           ("cat", one_hot, CATEGORICAL),
           ("num", "passthrough", NUMERIC),
       ],
       remainder="drop",
       sparse_threshold=0.0,
   )
   ```

   * `ColumnTransformer` is a special “meta‐transformer” in sklearn.
   * The `transformers` list has two elements:

     1. `("cat", one_hot, CATEGORICAL)`:

        * Name this transformer `"cat"`.
        * Use the `one_hot` transformer on the columns listed in the global `CATEGORICAL` list (these column names were gleaned from the YAML, everything whose dtype is `"enum"` or `"string"`, except the target).
     2. `("num", "passthrough", NUMERIC)`:

        * Name this transformer `"num"`.
        * For the columns listed in the global `NUMERIC` list (all ints, floats, datetimes), just “passthrough” → meaning “don’t apply any transformation; keep them as is.”
   * `remainder="drop"`:

     * If there are any columns in the DataFrame that are not listed in `CATEGORICAL` or `NUMERIC`, drop them silently. In other words, the final pipeline will only use the columns in CATEGORICAL ∪ NUMERIC, no extras.
   * `sparse_threshold=0.0`:

     * Normally, if only one transformer outputs a sparse matrix and the rest are dense, ColumnTransformer might convert the entire output to dense. By setting `sparse_threshold=0.0`, we say “as soon as any transformer output is sparse (which our one\_hot is), keep the entire output sparse.” This helps us not accidentally materialize a large dense matrix in memory.

4. **XGBClassifier instantiation**:

   ```python
   model = XGBClassifier(
       tree_method=tree_method,
       n_estimators=n_estimators,
       max_depth=max_depth,
       learning_rate=learning_rate,
       objective="binary:logistic",
       eval_metric="aucpr",
       use_label_encoder=False,
       verbosity=0,
   )
   ```

   * This creates a gradient‐boosted decision tree classifier with these hyperparameters:

     * `tree_method=tree_method` (usually “hist”).
     * `n_estimators=n_estimators` (e.g. 300).
     * `max_depth=max_depth` (e.g. 6).
     * `learning_rate=learning_rate` (e.g. 0.1).
   * `objective="binary:logistic"` tells XGBoost we want a binary classification with logistic loss.
   * `eval_metric="aucpr"` instructs XGBoost to compute the average precision (AUC-PR) on a validation set if we pass one. We won’t use early stopping in this baseline, but the model is built to optimize that metric.
   * `use_label_encoder=False` suppresses a warning about how XGBoost used to auto‐encode labels; now we specify it’s not needed.
   * `verbosity=0` means “no verbose XGBoost logs.” We rely on our own `logging`, not XGBoost’s built‐in console output.

5. **Assembling the full pipeline**:

   ```python
   pipeline = Pipeline(steps=[("prep", ct), ("clf", model)])
   return pipeline
   ```

   * `Pipeline` is a scikit-learn class that chains steps. Each step is a `(name, transformer_or_estimator)` pair.
   * Step “prep” is our `ColumnTransformer` (`ct`), and step “clf” is the `XGBClassifier`.
   * When you call `pipeline.fit(X_train, y_train)`, scikit-learn will do:

     1. `X_transformed = ct.fit_transform(X_train)`
     2. `clf.fit(X_transformed, y_train)`
   * At inference time (e.g. `pipeline.predict_proba(X_test)`), scikit-learn will do:

     1. `X_test_transformed = ct.transform(X_test)`
     2. `clf.predict_proba(X_test_transformed)`

By returning this `Pipeline` object, any caller simply does:

```python
pipe = build_pipeline(max_categories=100, n_estimators=300, max_depth=6, learning_rate=0.1)
pipe.set_params(clf__scale_pos_weight=spw)   # set the class‐weight inside XGBoost
pipe.fit(X_train, y_train)
```

---

## 5. MLflow setup helper

```python
def setup_mlflow(
    experiment_name: str,
    tracking_uri: str = "file:./mlruns",
) -> None:
    """
    Configure MLflow to use a local `mlruns/` directory and set up the experiment.

    If the experiment does not exist, it will be created (no error if it already exists).

    Args:
        experiment_name: Name of the MLflow experiment (e.g. "baseline_fraud").
        tracking_uri: Tracking URI (default: local folder "mlruns").
    """
    mlflow.set_tracking_uri(tracking_uri)
    try:
        mlflow.create_experiment(experiment_name)
    except mlflow.exceptions.MlflowException:
        # Experiment already exists; safe to ignore
        pass
    mlflow.set_experiment(experiment_name)
    logger.info("MLflow experiment set to '%s' at '%s'", experiment_name, tracking_uri)
```

MLflow is a tool for experiment tracking. When you “log a run,” MLflow records: parameters, metrics, artifacts (like model files), tags, and so forth, so you can review everything later in a UI.

1. **`mlflow.set_tracking_uri(tracking_uri)`**

   * We are telling MLflow, “Store all tracking data (runs, metrics, artifacts) under this URI.”
   * The default is `"file:./mlruns"`, which means “everything goes under the local folder `./mlruns/` in this working directory.” If you were pointing to a remote server, you might say `"http://my-mlflow-server:5000"`, but for Sprint 01 we use a local filesystem store.

2. **`mlflow.create_experiment(experiment_name)` inside a try/except**

   * We attempt to create a new MLflow experiment called, for example, `"baseline_fraud"`.
   * If that experiment already exists, `mlflow.create_experiment(...)` will throw an `MlflowException` saying “Experiment already exists.” We catch that and ignore it—no big deal if it’s already there.
   * The reason to create‐or‐open is to ensure that when we call `mlflow.start_run()`, it has a place to put metrics.

3. **`mlflow.set_experiment(experiment_name)`**

   * Tells MLflow, from now on, “use this experiment.” Any subsequent `mlflow.start_run()` will be associated with `"baseline_fraud"`.

4. **`logger.info("MLflow experiment set to '%s' at '%s'", ...)`**

   * Logs a message so you see in your console or CI logs:

     ```
     2025-06-05 12:35:05 [INFO] fraud_detection.modelling.train_baseline - MLflow experiment set to 'baseline_fraud' at 'file:./mlruns'
     ```

---

## 6. Quick‐train function for unit tests

```python
def quick_train(
    rows: int,
    parquet_path: pathlib.Path,
    *,
    save_model: bool = False,
    out_dir: pathlib.Path | None = None,
    seed: int = 42,
    max_categories: int = 100,
    n_estimators: int = 50,
    max_depth: int = 3,
    learning_rate: float = 0.1,
) -> tuple[float, pathlib.Path] | float:
    """
    A fast, in-memory train/test pass (used by unit tests).

    Steps:
      1. Load `rows` from `parquet_path` (random sample).
      2. Split 80/20 stratified.
      3. Build pipeline (OneHot + XGB) with small hyperparameters.
      4. Fit, predict, compute avg. precision (AUC-PR).
      5. If save_model=True, persist the fitted Pipeline to out_dir/baseline_xgb.pkl.

    Args:
        rows: Number of rows to sample for training+eval.
        parquet_path: Path to a small Parquet that matches SCHEMA.
        save_model: If True, pickle the fitted Pipeline into out_dir.
        out_dir: Directory to save model if save_model=True.
        seed: Random seed for reproducibility.
        max_categories: Maximum distinct categories passed to OneHotEncoder.
        n_estimators: Small number of XGB trees for a quick sanity check.
        max_depth: Depth for each tree.
        learning_rate: XGB learning rate.

    Returns:
        If save_model=False, returns only `auc_pr: float`.
        If save_model=True, returns `(auc_pr: float, model_path: pathlib.Path)`.
    """
    df = load_data(rows, parquet_path, seed=seed)
    if TARGET not in df.columns:
        raise KeyError(f"Target column '{TARGET}' missing from data.")

    X = df.drop(columns=[TARGET])
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    pipe = build_pipeline(
        max_categories=max_categories,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
    )
    spw = calc_class_weight(y_train)
    pipe.set_params(clf__scale_pos_weight=spw)
    pipe.fit(X_train, y_train)

    preds = pipe.predict_proba(X_test)[:, 1]
    auc_pr = average_precision_score(y_test, preds)

    if save_model:
        if out_dir is None:
            raise ValueError("out_dir must be provided if save_model=True.")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "baseline_xgb.pkl"
        import joblib

        joblib.dump(pipe, model_path)
        logger.info("Saved quick-test model to %s", model_path)
        return auc_pr, model_path

    return auc_pr
```

The purpose of `quick_train` is to allow our **unit tests** to verify “does a tiny model run end‐to‐end and produce an AUC-PR above a minimal threshold?” without having to load 1 million rows or do a full 300‐tree XGBoost.

Let’s go through it:

1. **Signature**:

   * We must pass `rows` (number of rows to sample) and `parquet_path` (where that Parquet is).
   * All other arguments are keyword‐only (because of the `*`), with default small values:

     * `save_model: bool = False` → if we want to keep the model artifact.
     * `out_dir: pathlib.Path | None = None` → where to write the model if `save_model=True`.
     * `seed: int = 42` → deterministic seed.
     * `max_categories: int = 100`
     * `n_estimators: int = 50` → a small number of trees for speed (instead of 300).
     * `max_depth: int = 3` → shallow trees for speed.
     * `learning_rate: float = 0.1`

   The **return type** is `tuple[float, pathlib.Path] | float`:

   * If `save_model=False`, we return a single float (the `auc_pr`).
   * If `save_model=True`, we return a 2-tuple `(auc_pr, model_path)`.

2. **Load data**:

   ```python
   df = load_data(rows, parquet_path, seed=seed)
   ```

   * Reuses the same `load_data` we explained above, but with smaller `rows`. For example, in a test we might call `quick_train(rows=200, parquet_path=tmp_path / "dummy.parquet")` and it gives back a Pandas DataFrame of 200 rows.

3. **Check target column**:

   ```python
   if TARGET not in df.columns:
       raise KeyError(f"Target column '{TARGET}' missing from data.")
   ```

   * Ensures the Parquet indeed had the column `label_fraud`. If not, we raise `KeyError` (the same kind of exception you’d get if you tried `df["label_fraud"]` on a missing column, but here we do it proactively with a clearer message).

4. **Split into X (features) and y (labels)**:

   ```python
   X = df.drop(columns=[TARGET])
   y = df[TARGET]
   ```

   * `df.drop(columns=[TARGET])` returns a new DataFrame without the `"label_fraud"` column. That DataFrame `X` contains everything else (all 23 feature columns).
   * `y = df[TARGET]` picks out a Pandas Series of the target variable (0 or 1 for nonfraud/fraud).

5. **Train/test split**:

   ```python
   X_train, X_test, y_train, y_test = train_test_split(
       X, y, test_size=0.2, stratify=y, random_state=seed
   )
   ```

   * Splits `X` and `y` into training and testing sets.
   * `test_size=0.2` means 20 % of the `rows` go to the test set, 80 % go to train.
   * `stratify=y` means “ensure the train and test sets have the same proportion of fraud vs. nonfraud as in `y`.” If `y` had 0.3 % fraud, then \~0.3 % of both the train and test sets will be fraud.
   * `random_state=seed` ensures reproducibility.

6. **Build the (small) pipeline**:

   ```python
   pipe = build_pipeline(
       max_categories=max_categories,
       n_estimators=n_estimators,
       max_depth=max_depth,
       learning_rate=learning_rate,
   )
   ```

   * We pass the smaller hyperparameters from the function arguments (e.g. `n_estimators=50`, `max_depth=3`).

7. **Compute class weight and inject it into the pipeline**:

   ```python
   spw = calc_class_weight(y_train)
   pipe.set_params(clf__scale_pos_weight=spw)
   ```

   * Recall `calc_class_weight(y_train)` returns `neg / pos` for the training set.
   * We then set `scale_pos_weight` for the XGBClassifier inside the pipeline. In a scikit-learn `Pipeline`, you address a parameter of a step by `"step_name__param_name"`. We named our model step `"clf"`, so `pipe.set_params(clf__scale_pos_weight=spw)` tells XGBoost how to adjust for class imbalance.
   * Now, when we call `pipe.fit(...)`, under the hood it will call `clf.fit(X_transformed, y_train, scale_pos_weight=spw)`.

8. **Fit the pipeline**:

   ```python
   pipe.fit(X_train, y_train)
   ```

   * This does two things:

     1. **`ct.fit_transform(X_train)`** – if there are any unseen categories in `X_train[ CATEGORICAL ]`, the encoder learns those. Numeric columns pass through.
     2. **`model.fit(X_train_transformed, y_train)`** – XGBoost builds 50 shallow trees on the transformed feature matrix.

9. **Compute predictions and AUC-PR**:

   ```python
   preds = pipe.predict_proba(X_test)[:, 1]
   auc_pr = average_precision_score(y_test, preds)
   ```

   * `pipe.predict_proba(X_test)` returns a 2D NumPy array of shape `(n_test_rows, 2)`, where column 0 is “predicted probability of class 0 (nonfraud)” and column 1 is “predicted probability of class 1 (fraud).”
   * We slice `[:, 1]` to keep only the probability of the positive class (fraud).
   * `average_precision_score(y_test, preds)` calculates the AUC under the precision‐recall curve. This is our test metric.

10. **If `save_model=True`, pickle the pipeline**:

    ```python
    if save_model:
        if out_dir is None:
            raise ValueError("out_dir must be provided if save_model=True.")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "baseline_xgb.pkl"
        import joblib

        joblib.dump(pipe, model_path)
        logger.info("Saved quick-test model to %s", model_path)
        return auc_pr, model_path
    ```

    * If the caller wants to keep the trained model, they must specify `save_model=True` and give an `out_dir` (a directory path).
    * We do `out_dir.mkdir(parents=True, exist_ok=True)` to create the directory if it doesn’t exist.
    * `model_path = out_dir / "baseline_xgb.pkl"` sets the file name to `baseline_xgb.pkl`.
    * `import joblib` is how we dump scikit-learn objects to disk. `joblib.dump(pipe, model_path)` writes the entire `Pipeline` (encoder + model) so that later you can do `joblib.load(model_path)` and get back the same pipeline.
    * We log an INFO message so the user knows where the file was saved.
    * Finally, we return `(auc_pr, model_path)`.

11. **Otherwise**:

    ```python
    return auc_pr
    ```

    * If `save_model=False`, we only return the float AUC-PR. This is how our unit tests will check “does `auc_pr > 0.005`?”

---

## 7. CLI argument parsing

```python
def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for full training run."""
    parser = argparse.ArgumentParser(description="Train baseline XGBoost fraud model.")
    parser.add_argument(
        "--rows",
        type=int,
        default=500_000,
        help="Number of rows to sample from Parquet for train+test.",
    )
    parser.add_argument(
        "--parquet",
        type=pathlib.Path,
        default=None,
        help="Path to a single Parquet with 1 000 000 simulated payments (24 columns).",
    )
    parser.add_argument("--n-est", type=int, default=300, help="Number of XGB trees.")
    parser.add_argument("--max-depth", type=int, default=6, help="Max depth per XGB tree.")
    parser.add_argument(
        "--learning-rate", type=float, default=0.1, help="XGB learning rate."
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=100,
        help="Max distinct categories per feature for OneHotEncoder.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--tree-method",
        type=str,
        default="hist",
        choices=["hist", "approx", "auto"],
        help="XGBoost `tree_method`.",
    )
    parser.add_argument(
        "--mlflow-experiment",
        type=str,
        default="baseline_fraud",
        help="Name of the MLflow experiment to log under.",
    )
    return parser.parse_args(args)
```

1. **`parser = argparse.ArgumentParser(...)`**

   * Creates a new command‐line argument parser. The `description` appears if you run `python train_baseline.py --help`.

2. **`--rows`**

   * `type=int` means the argument will be converted to an integer.
   * `default=500_000` means if the user doesn’t specify `--rows`, we will sample 500,000 rows by default.
   * The `help` string will be printed if you run `--help`.

3. **`--parquet`**

   * `type=pathlib.Path` means the parser will convert the string you type to a `Path` object.
   * `default=None` means if the user does not pass `--parquet`, we leave it as `None` and later do auto‐discovery.
   * The help text clarifies it should point to the 1 million-row simulated Parquet.

4. **`--n-est`, `--max-depth`, `--learning-rate`, `--max-categories`, `--seed`, `--tree-method`**

   * All these flags let the user override the hyperparameters in `build_pipeline(...)`.
   * For example, if you want to train 100 trees instead of 300, you can type `--n-est 100`.
   * For `--tree-method`, we provide a `choices=[...]` list. If you try to pass something not in that list, argparse will immediately error. Currently “hist”, “approx”, or “auto” are allowed.

5. **`--mlflow-experiment`**

   * `type=str` means it’s a simple string.
   * We default to `"baseline_fraud"`. If you have a different naming convention, you could say `--mlflow-experiment my_experiment_name`.

6. **`return parser.parse_args(args)`**

   * If `args` is `None` (the normal case), `parse_args(None)` will read from `sys.argv`. Otherwise, you can pass a custom list like `["--rows", "200", "--parquet", "data.pq"]` for testing.
   * The return value is a `Namespace` object whose attributes are the arguments. For example:

     ```python
     args = parse_args()
     print(args.rows)          # e.g. 500000
     print(args.parquet)       # e.g. Path("outputs/payments_1000000…")
     print(args.learning_rate) # e.g. 0.1
     ```

---

## 8. The `main()` function (the heart of the script)

```python
def main() -> None:
    """
    Main CLI function to train on up to --rows samples from a Parquet, fit XGB,
    compute AUC-PR, log everything to MLflow, and register the model as 'fraud_xgb'.
    """
    args = parse_args()
    try:
        # Resolve Parquet path if not provided
        if args.parquet is None:
            args.parquet = resolve_single_parquet(BASE_DIR / "outputs")
        logger.info("Using Parquet: %s", args.parquet)

        # Load data
        df = load_data(args.rows, args.parquet, seed=args.seed)
        if TARGET not in df.columns:
            raise KeyError(f"Target column '{TARGET}' missing from data.")
        X = df.drop(columns=[TARGET])
        y = df[TARGET]

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=args.seed
        )
        logger.info(
            "Train/test split: %d training rows, %d test rows; fraud rate: %.4f%% → %.4f%%",
            len(y_train),
            len(y_test),
            100 * (y.sum() / len(y)),
            100 * (y_test.sum() / len(y_test)),
        )

        # Build pipeline with user-specified hyperparameters
        pipeline = build_pipeline(
            max_categories=args.max_categories,
            n_estimators=args.n_est,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            tree_method=args.tree_method,
        )
        spw = calc_class_weight(y_train)
        pipeline.set_params(clf__scale_pos_weight=spw)

        # Set up MLflow
        setup_mlflow(args.mlflow_experiment, tracking_uri="file:./mlruns")
        with mlflow.start_run(run_name="baseline_xgb") as run:
            # Log parameters & tags
            mlflow.log_params(
                {
                    "rows": args.rows,
                    "n_estimators": args.n_est,
                    "max_depth": args.max_depth,
                    "learning_rate": args.learning_rate,
                    "scale_pos_weight": spw,
                    "train_timestamp": datetime.datetime.utcnow().isoformat(),
                    "seed": args.seed,
                }
            )
            mlflow.set_tag("schema_version", SCHEMA.get("version", "unknown"))
            mlflow.set_tag("git_commit", os.getenv("GIT_SHA", "local"))

            # Fit & evaluate
            pipeline.fit(X_train, y_train)
            preds = pipeline.predict_proba(X_test)[:, 1]
            auc_pr = average_precision_score(y_test, preds)
            mlflow.log_metric("auc_pr_test", auc_pr)
            logger.info("Test AUC-PR: %.4f", auc_pr)

            # Log pipeline (preprocessing + model) as a single sklearn artifact
            mlflow.sklearn.log_model(
                sk_model=pipeline,
                artifact_path="pipeline_artifact",
                registered_model_name="fraud_xgb",
            )

            # Log a small sample (1%) of the source data for traceability
            sample_df = df.sample(frac=0.01, random_state=args.seed)
            sample_path = BASE_DIR / "mlruns" / "tmp_sample.csv"
            sample_df.to_csv(sample_path, index=False)
            mlflow.log_artifact(str(sample_path), artifact_path="sample_source")
            sample_path.unlink()
            logger.info(
                "Run finished. AUC-PR=%.4f; run_id=%s",
                auc_pr,
                run.info.run_id,
            )
    except Exception as e:
        logger.exception("Training failed: %s", e)
        sys.exit(1)
```

The `main()` function glues everything together. It:

1. Parses arguments
2. Finds (or validates) the Parquet file
3. Loads and splits the data
4. Builds and trains the pipeline
5. Logs everything to MLflow
6. Catches any exception, logs it, and exits with an error code

Let’s go line by line:

1. **`args = parse_args()`**

   * Calls the function we just explained. `args` is now a namespace, e.g. `args.rows == 500000`, `args.parquet == None` (if not provided), `args.n_est == 300`, etc.

2. **`try:` … `except Exception as e:`**

   * We wrap the entire main body in a `try` block so that if anything goes wrong (missing file, invalid schema, XGBoost error, etc.), we catch it in one place.
   * In the `except` block, we do:

     ```python
     logger.exception("Training failed: %s", e)
     sys.exit(1)
     ```

     * `logger.exception(...)` logs the full stack trace at ERROR level.
     * `sys.exit(1)` quits Python with exit code 1, signalling failure to whatever invoked this script (e.g. CI). If everything goes well, `main()` ends normally without an explicit `sys.exit(0)` (0 is the default “success” code).

3. **Resolve the Parquet path**:

   ```python
   if args.parquet is None:
       args.parquet = resolve_single_parquet(BASE_DIR / "outputs")
   ```

   * If the user did not supply `--parquet somename.parquet`, then `args.parquet` is `None`. In that case, we call `resolve_single_parquet(BASE_DIR / "outputs")`, which will search under the `outputs/` directory for exactly one file matching the pattern `payments_*_1_000_000*.parquet`.
   * We’ll explain `resolve_single_parquet(...)` in Section 9. If it finds exactly one file, it returns the `Path` to it. Otherwise it throws a clear error.

4. **Log which Parquet we’re using**:

   ```python
   logger.info("Using Parquet: %s", args.parquet)
   ```

   * Example log:

     ```
     2025-06-05 12:35:00 [INFO] fraud_detection.modelling.train_baseline - Using Parquet: outputs/payments_1000000_1_000_000.parquet
     ```

5. **Load data**:

   ```python
   df = load_data(args.rows, args.parquet, seed=args.seed)
   ```

   * Exactly the same as the quick‐train function, but here `rows` is large (e.g. 500,000).
   * `df` is now a Pandas DataFrame with 500 000 rows and 24 columns.

6. **Check for target column again**:

   ```python
   if TARGET not in df.columns:
       raise KeyError(f"Target column '{TARGET}' missing from data.")
   ```

   * Redundant with `load_data`, but extra safety. If `label_fraud` is missing, bail out.

7. **Separate features and labels**:

   ```python
   X = df.drop(columns=[TARGET])
   y = df[TARGET]
   ```

   * Now `X` is a DataFrame with 23 columns, and `y` is a Series of length 500 000.

8. **Train/test split**:

   ```python
   X_train, X_test, y_train, y_test = train_test_split(
       X, y, test_size=0.2, stratify=y, random_state=args.seed
   )
   ```

   * Same as in `quick_train`, but now on a much larger dataset.
   * 80 % (400 000 rows) goes to training, 20 % (100 000 rows) to testing.

9. **Log the split statistics**:

   ```python
   logger.info(
       "Train/test split: %d training rows, %d test rows; fraud rate: %.4f%% → %.4f%%",
       len(y_train),
       len(y_test),
       100 * (y.sum() / len(y)),
       100 * (y_test.sum() / len(y_test)),
   )
   ```

   * This prints an INFO log with:

     * How many rows in training and test sets (`len(y_train)` and `len(y_test)`). Here, `len(y_train)` = 400 000, `len(y_test)` = 100 000.
     * The overall fraud rate in the full dataset: `100 * (y.sum() / len(y))`. If `y.sum()` is 1 200 (0.24 % of 500 000), it prints “0.2400%”.
     * The fraud rate in the test set: `100 * (y_test.sum() / len(y_test))`. Because of stratification, this should be almost identical to the overall rate.
   * Example:

     ```
     2025-06-05 12:36:00 [INFO] fraud_detection.modelling.train_baseline - Train/test split: 400000 training rows, 100000 test rows; fraud rate: 0.3000% → 0.3000%
     ```

10. **Build the full pipeline**:

    ```python
    pipeline = build_pipeline(
        max_categories=args.max_categories,
        n_estimators=args.n_est,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        tree_method=args.tree_method,
    )
    ```

    * We pass the hyperparameters the user specified (or the defaults). Now `pipeline` is the object described in Section 4.3. It knows how to one‐hot encode the categorical features, passthrough numeric ones, and then train an XGBoost model with 300 trees, max depth 6, learning rate 0.1, using the “hist” method, etc.

11. **Compute and set class weight**:

    ```python
    spw = calc_class_weight(y_train)
    pipeline.set_params(clf__scale_pos_weight=spw)
    ```

    * We compute `neg / pos` on the 400 000 training rows (maybe \~398 800 nonfraud vs. 1 200 fraud → ratio \~ 332.33).
    * We tell the pipeline to set `clf__scale_pos_weight=332.33`. This ensures the XGBoost model correctly accounts for the class imbalance.

12. **Set up MLflow**:

    ```python
    setup_mlflow(args.mlflow_experiment, tracking_uri="file:./mlruns")
    ```

    * Calls the helper from Section 5. If the experiment “baseline\_fraud” doesn’t exist, it creates it. Then any subsequent runs all get filed under that experiment in `./mlruns`.

13. **`with mlflow.start_run(run_name="baseline_xgb") as run:`**

    * Starts a new MLflow run, giving it the human‐readable name “baseline\_xgb.” The returned object `run` has attributes like `run.info.run_id` (a unique identifier). Everything logged inside this `with` block belongs to that run.

14. **Log parameters**:

    ```python
    mlflow.log_params(
        {
            "rows": args.rows,
            "n_estimators": args.n_est,
            "max_depth": args.max_depth,
            "learning_rate": args.learning_rate,
            "scale_pos_weight": spw,
            "train_timestamp": datetime.datetime.utcnow().isoformat(),
            "seed": args.seed,
        }
    )
    ```

    * `mlflow.log_params(...)` takes a dictionary of key→value pairs. MLflow records these as the run’s “parameters.”
    * We log exactly which `rows` (500 000), `n_estimators` (300), `max_depth` (6), `learning_rate` (0.1), `scale_pos_weight` (332.33), current timestamp (UTC), and `seed` (42).
    * This means later, in the MLflow UI, you can see exactly which hyperparameters and random seed were used.

15. **Log tags**:

    ```python
    mlflow.set_tag("schema_version", SCHEMA.get("version", "unknown"))
    mlflow.set_tag("git_commit", os.getenv("GIT_SHA", "local"))
    ```

    * Tags are like metadata. We set:

      * `schema_version` to whatever was in the YAML (for example, `"0.1.0"`). If the YAML had no top-level `version` field, we’d default to `"unknown"`.
      * `git_commit` to the environment variable `GIT_SHA` if available; otherwise, `"local"`. In CI, you could set `GIT_SHA=$(git rev-parse HEAD)` so that runs are linked to the exact commit. Locally, it will just record `"local"`.

16. **Fit the pipeline and evaluate**:

    ```python
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict_proba(X_test)[:, 1]
    auc_pr = average_precision_score(y_test, preds)
    mlflow.log_metric("auc_pr_test", auc_pr)
    logger.info("Test AUC-PR: %.4f", auc_pr)
    ```

    * **`pipeline.fit(X_train, y_train)`**:

      1. The pipeline’s “prep” step (`ColumnTransformer`) calls `one_hot.fit_transform(X_train[CATEGORICAL])` and “passthrough” on `X_train[NUMERIC]`. This yields a feature matrix in sparse format.
      2. The “clf” step (`XGBClassifier`) calls `.fit(...)` on that feature matrix. Because we earlier set `clf__scale_pos_weight` to the class‐weight float, XGBoost uses that ratio.
    * **`preds = pipeline.predict_proba(X_test)[:, 1]`**:

      * At inference time, the pipeline’s `ColumnTransformer` again transforms `X_test` to a sparse feature matrix (one‐hot encode, passthrough numeric). Then XGBoost’s `.predict_proba(...)` yields probabilities. We slice `[:, 1]` for the positive‐class (fraud) probability.
    * **`auc_pr = average_precision_score(y_test, preds)`**:

      * Compares the true labels `y_test` with predicted probabilities to compute AUC-PR.
    * **`mlflow.log_metric("auc_pr_test", auc_pr)`**:

      * Records this metric in the MLflow run under the key `"auc_pr_test"`. Now if you open MLflow UI, you’ll see a graph of AUC-PR over time (over multiple runs).
    * **`logger.info("Test AUC-PR: %.4f", auc_pr)`**

      * Logs to console so you can see something like:

        ```
        2025-06-05 12:40:30 [INFO] fraud_detection.modelling.train_baseline - Test AUC-PR: 0.7321
        ```

17. **Log the entire Pipeline as an artifact**:

    ```python
    mlflow.sklearn.log_model(
        sk_model=pipeline,
        artifact_path="pipeline_artifact",
        registered_model_name="fraud_xgb",
    )
    ```

    * This call tells MLflow:

      * “Take the `pipeline` object (which includes the `ColumnTransformer` and the trained `XGBClassifier`), and save it under the `artifact_path` folder called `pipeline_artifact`.”
      * Then register it under the model registry name `"fraud_xgb"`. The first time this runs, MLflow will create `fraud_xgb` model version 1.
    * Later, you can load it from MLflow with:

      ```python
      loaded_pipeline = mlflow.pyfunc.load_model("models:/fraud_xgb/1")
      ```

      or something similar.

18. **Log a small sample of the raw data**:

    ```python
    sample_df = df.sample(frac=0.01, random_state=args.seed)
    sample_path = BASE_DIR / "mlruns" / "tmp_sample.csv"
    sample_df.to_csv(sample_path, index=False)
    mlflow.log_artifact(str(sample_path), artifact_path="sample_source")
    sample_path.unlink()
    ```

    * We take **1 %** of the entire `df` (which has 500 000 rows) to produce a 5 000-row sample.
    * We write that sample to a temporary CSV file at `mlruns/tmp_sample.csv`.
    * We call `mlflow.log_artifact(...)` to save that CSV under the run’s `"sample_source"` folder.
    * Finally, we delete the local `tmp_sample.csv`, because we don’t want to leave large files around.
    * This ensures that anyone inspecting the MLflow run can download that sample CSV to see exactly what the input distribution looked like (rather than having to fetch the entire 500 000-row Parquet).

19. **Log final message**:

    ```python
    logger.info(
        "Run finished. AUC-PR=%.4f; run_id=%s",
        auc_pr,
        run.info.run_id,
    )
    ```

    * We log an INFO message saying “Run finished. AUC-PR=0.7321; run\_id=abc123…”.
    * `run.info.run_id` is the unique ID MLflow assigned to this run (e.g. `"6c4b1a2e7c8e..."`).

20. **End of `with mlflow.start_run(...)`**

    * Exiting the `with` block automatically ends the MLflow run, writing out all tracked data to the `mlruns/` folder.

21. **`except Exception as e:`**

    ```python
    except Exception as e:
        logger.exception("Training failed: %s", e)
        sys.exit(1)
    ```

    * If any part of the above (resolving Parquet, loading data, splitting, building pipeline, fitting, logging to MLflow, writing sample CSV) throws an exception, we catch it here.
    * `logger.exception(...)` prints the exception message plus a full stack trace at ERROR level.
    * `sys.exit(1)` terminates the program with code 1, so in CI you see a failing job.

At the very end of `main()`, if nothing fails, the function returns `None` implicitly and the script finishes with exit code 0 (success).

---

## 9. Resolving the Parquet file automatically

```python
def resolve_single_parquet(outputs_dir: pathlib.Path) -> pathlib.Path:
    """
    Search for exactly one 'payments_*_1_000_000*.parquet' under outputs_dir.
    Raise if zero or >1 matches.
    """
    if not outputs_dir.exists() or not outputs_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory at {outputs_dir}")
    candidates = list(outputs_dir.glob("payments_*_1_000_000*.parquet"))
    if len(candidates) == 0:
        raise FileNotFoundError(f"No matching Parquet files under {outputs_dir}")
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise RuntimeError(f"Multiple candidate Parquets found: {names}")
    return candidates[0]
```

When the user does *not* pass `--parquet somefile.parquet`, we want a convenient default: look under `outputs/` for a file that matches the pattern `payments_*_1_000_000*.parquet`. Usually your data generator writes something like `outputs/payments_1000000_1_000_000.parquet`, but perhaps it could be `payments_1000000_abcdef.parquet`. This helper makes sure:

1. **Signature**:

   * We pass `outputs_dir: pathlib.Path` (usually `BASE_DIR / "outputs"`).
   * We return a single `pathlib.Path` to the Parquet file.

2. **Check that `outputs_dir` exists and is a directory**:

   ```python
   if not outputs_dir.exists() or not outputs_dir.is_dir():
       raise FileNotFoundError(f"Expected a directory at {outputs_dir}")
   ```

   * If you accidentally typed `--parquet` or `OUTPUTS` incorrectly in your shell, you get a clear error.

3. **Find candidate files**:

   ```python
   candidates = list(outputs_dir.glob("payments_*_1_000_000*.parquet"))
   ```

   * `outputs_dir.glob(...)` returns a generator of all files under `outputs/` matching that glob pattern:

     * `payments_` at the start,
     * followed by anything (`*`),
     * then `_1_000_000` in the middle (the 1 million row marker),
     * then anything (`*`),
     * then `.parquet` at the end.
   * Converting it to `list(...)` collects them all into a Python list of `Path` objects.

4. **Zero matches**:

   ```python
   if len(candidates) == 0:
       raise FileNotFoundError(f"No matching Parquet files under {outputs_dir}")
   ```

   * If there is no file matching that pattern, we tell the user “we couldn’t find anything under `outputs/`. Did you run the data generator?”

5. **More than one match**:

   ```python
   if len(candidates) > 1:
       names = ", ".join(p.name for p in candidates)
       raise RuntimeError(f"Multiple candidate Parquets found: {names}")
   ```

   * If there’s more than one candidate (e.g. you accidentally left an old file `payments_old_1_000_000.parquet` and a new one `payments_new_1_000_000.parquet`), we don’t want to pick one arbitrarily. We raise an error listing all file names so you can decide which one to delete.

6. **Exactly one match**:

   ```python
   return candidates[0]
   ```

   * If there is exactly one, that’s our Parquet. We return it to `main()`, which then uses it in `load_data(...)`.

---

## 10. Putting it all together: how you’d actually run this

Suppose you have:

* Cloned the repository to `/home/student/fraud-detection-system/`.
* Generated your Parquet via `make gen-data-raw` so that you have exactly one file:

  ```
  /home/student/fraud-detection-system/outputs/payments_1000000_1_000_000.parquet
  ```
* You want to train on 500 000 rows and log the results to MLflow. You’d open a terminal, activate your Poetry environment, and run:

```bash
poetry run python -m fraud_detection.modelling.train_baseline --rows 500000
```

Since you did not supply `--parquet`, inside `main()`:

1. `parse_args()` gives `args.parquet = None`.

2. `resolve_single_parquet(BASE_DIR/"outputs")` finds that one Parquet file, returns its path.

3. We log “Using Parquet: outputs/payments\_1000000\_1\_000\_000.parquet.”

4. We call `load_data(500000, Path("outputs/payments_…"))`, which samples 500 000 rows randomly.

5. We split, build pipeline, etc.

6. In MLflow, the new run appears under experiment “baseline\_fraud.” It logs parameters:

   ```
   rows=500000  
   n_estimators=300  
   max_depth=6  
   learning_rate=0.1  
   scale_pos_weight=332.333…  
   train_timestamp=2025-06-05T12:36:00  
   seed=42
   ```

   plus tags:

   ```
   schema_version=0.1.0  
   git_commit=local  (unless you explicitly set GIT_SHA in your environment)  
   ```

   plus metrics:

   ```
   auc_pr_test=0.7321
   ```

   plus artifacts:

   * The entire pipeline saved under “pipeline\_artifact” (so MLflow stores a ZIP containing the pipeline pickle, software environment info, etc.)
   * A tiny CSV named `tmp_sample.csv` under `sample_source`, with 1% of the 500 000 rows (5 000 rows) so you can inspect input distributions.

7. On your console, you also see logs:

   ```
   2025-06-05 12:35:00 [INFO] train_baseline - Using Parquet: outputs/payments_…parquet  
   2025-06-05 12:35:02 [INFO] train_baseline - Loaded 500000 rows from payments_…parquet  
   2025-06-05 12:35:03 [INFO] train_baseline - Train/test split: 400000 training rows, 100000 test rows; fraud rate: 0.3000% → 0.3000%  
   2025-06-05 12:40:30 [INFO] train_baseline - Test AUC-PR: 0.7321  
   2025-06-05 12:40:32 [INFO] train_baseline - Run finished. AUC-PR=0.7321; run_id=6c4b1a2e7c8e…
   ```

---

## 11. Recap of key points for a CS student

1. **Separation of concerns**:

   * We kept all data‐loading logic in `load_data(...)`.
   * We kept feature‐engineering & model specification in `build_pipeline(...)`.
   * We keep MLflow setup in `setup_mlflow(...)`.
   * We keep a quick, testable routine in `quick_train(...)`.
   * `main()` only orchestrates: parse arguments, call these helpers, catch exceptions.

2. **Why Polars → Pandas?**

   * Polars can read and sample a Parquet file faster and with lower memory than Pandas.
   * But XGBoost and scikit-learn expect a Pandas DataFrame (or NumPy arrays). So we read with Polars, sample, then convert to Pandas once it’s small enough.

3. **Why a scikit-learn `Pipeline`?**

   * It bundles preprocessing (one‐hot encoding + passthrough) and the model (XGBoost) into a single object.
   * This is crucial when you want to serialize (pickle) the entire end-to-end data transformation + model in one go. Later, you can do:

     ```python
     loaded_pipeline = joblib.load("baseline_xgb.pkl")
     predictions = loaded_pipeline.predict_proba(new_transactions_df)[:,1]
     ```

     without rewriting any code.

4. **`ColumnTransformer`**:

   * Think of it as “apply different preprocessing steps to different subsets of columns.”
   * CATEGORICAL → one hot encode (turn each category value into 0/1 columns).
   * NUMERIC → passthrough (leave them as numbers).
   * Combine the results into one large feature matrix.

5. **Class weighting**:

   * Because fraud is very rare (\~0.3%), XGBoost would “learn” to predict everything as nonfraud and still be >99% accurate. That’s why we compute `scale_pos_weight = negative_count / positive_count`.
   * Setting `scale_pos_weight=332` tells XGBoost to weight fraud examples 332× more. This forces the model to pay attention to the small number of fraud rows.

6. **MLflow tracking**:

   * Instead of printing the AUC-PR to your terminal and hoping you remember it, MLflow records it in a folder (`mlruns/`).
   * You can launch `mlflow ui` (or “make mlflow-ui”) and see a table of runs, each with its parameters and final metric. You can compare dozens of runs at once.

7. **Error handling and logging**:

   * We never just let Python crash with a cryptic traceback in CI. Instead, if any step fails, we call `logger.exception(..)` so the stack trace is printed with our uniform log format. Then we `sys.exit(1)` so CI knows “this step failed.”
   * We also do checks like “does the file exist?”, “are there enough rows to sample?”, “does the schema contain the `label_fraud` column?”, “how many Parquet files match my pattern?”, etc. That prevents subtle bugs later on.

8. **Unit‐test-friendly design**:

   * We created `quick_train(...)` to spin up a tiny model (50 trees, depth 3) on a randomly sampled subset of a Parquet.
   * But our tests don’t even need a real Parquet under `outputs/`; they can generate their own small Parquet (e.g. 1 000 rows) in a temporary directory, then call `quick_train(rows=200, parquet_path=tmp_path/"dummy.parquet")`.
   * This ensures that CI tests are extremely fast (under 10 seconds) and do not depend on any external files.

---

## 12. Final thoughts

* Reading this code as a third-year CS student, you should now see that each helper function has a single responsibility. For example:

  * **`load_schema(...)`** → “load and validate the YAML schema.”
  * **`load_data(...)`** → “sample X rows from a Parquet file and return a Pandas DataFrame.”
  * **`calc_class_weight(...)`** → “compute the ratio of nonfraud to fraud.”
  * **`build_pipeline(...)`** → “assemble a one‐hot + XGBoost pipeline.”
  * **`setup_mlflow(...)`** → “initialize MLflow experiment.”
  * **`quick_train(...)`** → “train a tiny model for unit tests.”
  * **`parse_args(...)`** → “define and read CLI flags.”
  * **`main()`** → “orchestrate everything in production mode.”
  * **`resolve_single_parquet(...)`** → “find exactly one Parquet in `outputs/`.”

* Modern Python practice (especially in data‐science or MLOps contexts) relies heavily on these tools:

  * **Polars** for fast data processing (you’ll see this more in industry as data volumes grow).
  * **scikit-learn `Pipeline` and `ColumnTransformer`** to keep your data transformations and model training neatly packaged together.
  * **XGBoost** as a high‐performance, widely used gradient boosting library for tabular data.
  * **MLflow** as a minimal dependency experiment tracker—no need to set up a complicated database; we can just write to `./mlruns` locally.
  * **`argparse`** for making your scripts flexible and repeatable: if you need to change hyperparameters or sample size, you don’t modify the code; you just pass different flags.

* Every line has been chosen to satisfy production‐grade requirements:

  * **Robustness** (check file existence, check for multiple Parquets).
  * **Reproducibility** (explicit seeds, saving a schema version, tagging Git SHA).
  * **Observability** (detailed logging, MLflow tracking).
  * **Modularity** (well‐factored functions, type hints, docstrings).
  * **Testability** (the `quick_train` function is explicitly designed for tests, and it does not rely on huge external data files).

By stepping through each line and understanding how Polars, Pandas, scikit-learn, XGBoost, and MLflow interact, you now have a clear picture of:

1. **Data ingestion** → “sample from Parquet.”
2. **Preprocessing** → “one‐hot encode categoricals, passthrough numeric.”
3. **Model training** → “train a balanced XGBoost model.”
4. **Evaluation** → “compute AUC-PR.”
5. **Tracking** → “log params, metrics, artifacts to MLflow.”

This is exactly how a real‐world ML pipeline is structured when you aim for production quality. Take your time to re‐read any section that feels unfamiliar (for example, if you’ve never used `Pipeline` before, try a small toy example in a Python REPL). But from here on, you have a complete blueprint for how a baseline model training script should be written, tested, and run in a professional setting.

Let me know if any specific part still feels unclear, but at this point you should be able to trace every variable, every transformation, and every external call in the code.
