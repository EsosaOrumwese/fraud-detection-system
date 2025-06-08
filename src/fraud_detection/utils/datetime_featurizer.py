from sklearn.base import BaseEstimator, TransformerMixin  # type: ignore
import pandas as pd  # type: ignore
import numpy as np


class DateTimeFeaturizer(BaseEstimator, TransformerMixin):
    """
    Transformer that converts datetime columns into numeric features:
      - hour, day_of_week, day, month, is_weekend
      - optional cyclic encoding for hour_of_day
    """

    def __init__(self, fields: list[str], cyclical: bool = True):
        self.fields = fields
        self.cyclical = cyclical

    def fit(self, X: pd.DataFrame, y=None):
        # no fitting needed
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not all(col in X.columns for col in self.fields):
            missing = set(self.fields) - set(X.columns)
            raise KeyError(f"Missing datetime columns: {missing}")
        df = pd.DataFrame(index=X.index)
        for col in self.fields:
            ts = pd.to_datetime(X[col], errors="coerce")
            if ts.isna().any():
                raise ValueError(f"Nulls found after parsing datetime in '{col}'")
            df[f"{col}_hour"] = ts.dt.hour
            df[f"{col}_dow"] = ts.dt.dayofweek
            df[f"{col}_day"] = ts.dt.day
            df[f"{col}_month"] = ts.dt.month
            df[f"{col}_is_wkend"] = ts.dt.dayofweek.isin([5, 6]).astype(int)
            if self.cyclical:
                df[f"{col}_hour_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24)
                df[f"{col}_hour_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24)
        return df
