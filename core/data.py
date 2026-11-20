from functools import lru_cache
from pathlib import Path

import pandas as pd

PARQUET = Path(__file__).resolve().parent.parent / "data" / "immobilier.parquet"


@lru_cache(maxsize=1)
def get_df() -> pd.DataFrame:
    """Charge le parquet une seule fois pour tout le processus."""
    df = pd.read_parquet(PARQUET)
    df["type"] = df["type"].astype("category")
    return df
