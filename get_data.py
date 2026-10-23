"""Step 1 - download the 84.51° Complete Journey files and load them as clean tables."""
import urllib.request

import pandas as pd
import pyreadr

from . import config


def download(force: bool = False) -> None:
    """Download the raw files into data/raw/ (skips files that are already there)."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, filename in config.SOURCE_FILES.items():
        target = config.RAW_DIR / filename
        if target.exists() and not force:
            continue
        print(f"  downloading {filename} ...")
        urllib.request.urlretrieve(config.SOURCE_URL + filename, target)


def _read(filename: str) -> pd.DataFrame:
    return list(pyreadr.read_r(str(config.RAW_DIR / filename)).values())[0]


def _to_int(s: pd.Series) -> pd.Series:
    # A few IDs were saved in scientific notation (e.g. "9e+05" for product 900000), so parse as numbers first.
    return pd.to_numeric(s, errors="raise").astype("int64")


def load() -> dict:
    """Return every table as a pandas DataFrame with tidy column types."""
    t = {name: _read(fn) for name, fn in config.SOURCE_FILES.items()}

    for name in ["campaigns", "campaign_descriptions", "coupons", "coupon_redemptions"]:
        t[name]["campaign_id"] = _to_int(t[name]["campaign_id"])
    for name in ["campaigns", "coupon_redemptions", "demographics", "transactions"]:
        t[name]["household_id"] = _to_int(t[name]["household_id"])
    for name in ["coupons", "products", "transactions"]:
        t[name]["product_id"] = _to_int(t[name]["product_id"])

    cd = t["campaign_descriptions"]
    cd["campaign_type"] = cd["campaign_type"].astype(str)
    cd["start_date"] = pd.to_datetime(cd["start_date"])
    cd["end_date"] = pd.to_datetime(cd["end_date"])

    t["coupon_redemptions"]["redemption_date"] = pd.to_datetime(t["coupon_redemptions"]["redemption_date"])
    t["products"]["brand"] = t["products"]["brand"].astype(str)

    tx = t["transactions"]
    tx["ts"] = pd.to_datetime(tx["transaction_timestamp"])
    tx["basket_id"] = _to_int(tx["basket_id"])
    tx = tx.merge(t["products"][["product_id", "department", "brand"]], on="product_id", how="left")
    t["transactions"] = tx
    return t
