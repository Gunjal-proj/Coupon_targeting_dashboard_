"""Step 2 - one row per (household, campaign).

Every feature uses ONLY what happened before the campaign started. This is the rule all five
AmExpert 2019 winners stressed: a model that peeks at the future looks great in testing and
fails in real life.
"""
import numpy as np
import pandas as pd

from . import config

AGE_ORDER = ["19-24", "25-34", "35-44", "45-54", "55-64", "65+"]
INCOME_ORDER = ["Under 15K", "15-24K", "25-34K", "35-49K", "50-74K", "75-99K",
                "100-124K", "125-149K", "150-174K", "175-199K", "200-249K", "250K+"]
SIZE_MAP = {"1": 1, "2": 2, "3": 3, "4": 4, "5+": 5}
KIDS_MAP = {"0": 0, "1": 1, "2": 2, "3+": 3}

# Columns the models are allowed to use (all known before the campaign starts).
MODEL_FEATURES = [
    # shopping habits
    "spend_per_week", "baskets_per_week", "avg_basket_value", "days_since_last_visit",
    "recent_spend_per_week", "spend_trend", "n_departments",
    # deal behaviour
    "coupon_line_rate", "coupon_savings_share", "promo_line_rate", "private_label_share",
    # past campaign behaviour
    "prior_campaigns_received", "prior_campaigns_redeemed", "prior_redemptions", "prior_redeem_rate",
    # overlap between the campaign's coupons and what the household already buys (winners' key idea)
    "coupons_matched", "coupons_matched_share", "coupons_matched_with_coupon",
    "coupon_products_bought", "coupon_product_spend_per_week",
    # campaign attributes
    "is_type_a", "n_coupons", "campaign_days",
    # demographics (only about half of households have them)
    "age_rank", "income_rank", "household_size", "kids_count",
]


def build(t: dict) -> pd.DataFrame:
    cd = t["campaign_descriptions"]
    camp = t["campaigns"].merge(cd, on="campaign_id")
    coupons = t["coupons"]
    red = t["coupon_redemptions"]
    tx = t["transactions"].copy()
    tx["coupon_flag"] = (tx["coupon_disc"] > 0).astype(int)
    tx["promo_flag"] = (tx["retail_disc"] > 0).astype(int)
    tx["private_spend"] = np.where(tx["brand"] == "Private", tx["sales_value"], 0.0)
    data_start = pd.Timestamp(config.DATA_START)

    frames = []
    for c in cd.sort_values("start_date").itertuples(index=False):
        start = c.start_date
        hh = camp.loc[camp.campaign_id == c.campaign_id, "household_id"].unique()
        df = pd.DataFrame({"household_id": hh, "campaign_id": c.campaign_id})

        history_days = max((start - data_start).days, 0)
        weeks = history_days / 7
        recent_weeks = min(config.RECENT_DAYS, history_days) / 7

        hist = tx[(tx["ts"] < start) & tx["household_id"].isin(hh)]
        recent = hist[hist["ts"] >= start - pd.Timedelta(days=config.RECENT_DAYS)]

        agg = hist.groupby("household_id").agg(
            n_baskets=("basket_id", "nunique"),
            spend=("sales_value", "sum"),
            n_lines=("sales_value", "size"),
            coupon_lines=("coupon_flag", "sum"),
            coupon_savings=("coupon_disc", "sum"),
            promo_lines=("promo_flag", "sum"),
            private_spend=("private_spend", "sum"),
            n_departments=("department", "nunique"),
            last_ts=("ts", "max"),
        )
        agg["recent_spend"] = recent.groupby("household_id")["sales_value"].sum()

        # Coupons in this campaign and the products each one can be used on
        cc = coupons.loc[coupons.campaign_id == c.campaign_id, ["coupon_upc", "product_id"]].drop_duplicates()
        n_coupons = cc["coupon_upc"].nunique()
        h_cp = hist[hist["product_id"].isin(cc["product_id"].unique())]
        bought = h_cp[["household_id", "product_id"]].drop_duplicates()
        bought_with_coupon = h_cp.loc[h_cp["coupon_flag"] == 1, ["household_id", "product_id"]].drop_duplicates()
        agg["coupons_matched"] = bought.merge(cc, on="product_id").groupby("household_id")["coupon_upc"].nunique()
        agg["coupons_matched_with_coupon"] = (
            bought_with_coupon.merge(cc, on="product_id").groupby("household_id")["coupon_upc"].nunique())
        agg["coupon_products_bought"] = bought.groupby("household_id")["product_id"].nunique()
        agg["coupon_product_spend"] = h_cp.groupby("household_id")["sales_value"].sum()

        # Past campaign behaviour (strictly before this campaign started)
        prior_c = camp[(camp.start_date < start) & camp.household_id.isin(hh)]
        prior_r = red[(red.redemption_date < start) & red.household_id.isin(hh)]
        agg = agg.reindex(hh)
        agg["prior_campaigns_received"] = prior_c.groupby("household_id")["campaign_id"].nunique()
        agg["prior_campaigns_redeemed"] = prior_r.groupby("household_id")["campaign_id"].nunique()
        agg["prior_redemptions"] = prior_r.groupby("household_id").size()

        df = df.merge(agg, left_on="household_id", right_index=True, how="left")

        # Outcome: did the household redeem at least one coupon from this campaign?
        this_red = red[red.campaign_id == c.campaign_id]
        df["coupons_redeemed"] = df["household_id"].map(this_red.groupby("household_id").size()).fillna(0).astype(int)
        df["redeemed"] = (df["coupons_redeemed"] > 0).astype(int)

        df["campaign_type"] = c.campaign_type
        df["start_date"] = start
        df["end_date"] = c.end_date
        df["campaign_days"] = (c.end_date - start).days
        df["n_coupons"] = n_coupons
        df["history_days"] = history_days
        df["_weeks"] = weeks
        df["_recent_weeks"] = recent_weeks
        frames.append(df)

    d = pd.concat(frames, ignore_index=True)

    count_cols = ["n_baskets", "spend", "n_lines", "coupon_lines", "coupon_savings", "promo_lines",
                  "private_spend", "n_departments", "recent_spend", "coupons_matched",
                  "coupons_matched_with_coupon", "coupon_products_bought", "coupon_product_spend",
                  "prior_campaigns_received", "prior_campaigns_redeemed", "prior_redemptions"]
    d[count_cols] = d[count_cols].fillna(0)

    w = d["_weeks"].replace(0, np.nan)
    rw = d["_recent_weeks"].replace(0, np.nan)
    d["spend_per_week"] = d["spend"] / w
    d["baskets_per_week"] = d["n_baskets"] / w
    d["avg_basket_value"] = (d["spend"] / d["n_baskets"].replace(0, np.nan)).fillna(0)
    d["days_since_last_visit"] = ((d["start_date"] - d["last_ts"]).dt.total_seconds() / 86400).fillna(d["history_days"])
    d["recent_spend_per_week"] = d["recent_spend"] / rw
    d["spend_trend"] = (d["recent_spend_per_week"] / d["spend_per_week"].replace(0, np.nan)).fillna(0)
    d["coupon_line_rate"] = (d["coupon_lines"] / d["n_lines"].replace(0, np.nan)).fillna(0)
    d["coupon_savings_share"] = (d["coupon_savings"] / d["spend"].replace(0, np.nan)).fillna(0)
    d["promo_line_rate"] = (d["promo_lines"] / d["n_lines"].replace(0, np.nan)).fillna(0)
    d["private_label_share"] = (d["private_spend"] / d["spend"].replace(0, np.nan)).fillna(0)
    d["prior_redeem_rate"] = (d["prior_campaigns_redeemed"] / d["prior_campaigns_received"].replace(0, np.nan)).fillna(0)
    d["coupons_matched_share"] = d["coupons_matched"] / d["n_coupons"]
    d["coupon_product_spend_per_week"] = d["coupon_product_spend"] / w
    d["is_type_a"] = (d["campaign_type"] == "Type A").astype(int)

    dem = t["demographics"].copy()
    dem["age_rank"] = dem["age"].astype(str).map({v: i for i, v in enumerate(AGE_ORDER)})
    dem["income_rank"] = dem["income"].astype(str).map({v: i for i, v in enumerate(INCOME_ORDER)})
    dem["household_size"] = dem["household_size"].astype(str).map(SIZE_MAP)
    dem["kids_count"] = dem["kids_count"].astype(str).map(KIDS_MAP)
    d = d.merge(dem[["household_id", "age_rank", "income_rank", "household_size", "kids_count"]],
                on="household_id", how="left")

    d["has_history"] = d["history_days"] >= config.MIN_HISTORY_DAYS
    return d.drop(columns=["_weeks", "_recent_weeks", "last_ts"])
