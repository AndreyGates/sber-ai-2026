import pandas as pd

from .config import DATA_CSV


def load_dataset() -> list[dict]:
    df = pd.read_csv(DATA_CSV)
    df = df.dropna(subset=["code"])
    df = df[df["code"].str.strip().str.len() > 0]
    df = df.drop_duplicates(subset=["unique_id"])
    return df.to_dict("records")
