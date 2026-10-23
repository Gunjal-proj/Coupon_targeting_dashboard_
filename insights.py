"""Step 4 - marketing insights: campaign tracker, what drives redemption, segments, and the
"would they have bought anyway?" check."""
import numpy as np
import pandas as pd

from . import config

TYPE_NOTES = {
    "Type A": "Personalised: each household got 16 coupons picked from a pool using its past purchases.",
    "Type B": "Mass: every household in the campaign got every coupon.",
    "Type C": "Mass: every household in the campaign got every coupon.",
}


def _rate_table(df: pd.DataFrame, col: str, bins, labels) -> list:
    b = pd.cut(df[col], bins=bins, labels=labels)
    g = df.groupby(b, observed=True)["redeemed"].agg(["size", "sum", "mean"])
    return [{"label": str(k), "n": int(r["size"]), "redeemers": int(r["sum"]), "rate": float(r["mean"])}
            for k, r in g.iterrows()]


def kpis(t: dict, d: pd.DataFrame) -> dict:
    cd = t["campaign_descriptions"]
    return {
        "households_in_study": int(t["transactions"]["household_id"].nunique()),
        "households_mailed": int(t["campaigns"]["household_id"].nunique()),
        "campaigns": int(cd["campaign_id"].nunique()),
        "mailings": int(len(d)),
        "redeeming_mailings": int(d["redeemed"].sum()),
        "redemption_rate": float(d["redeemed"].mean()),
        "no_redemption_share": float(1 - d["redeemed"].mean()),
        "coupons_redeemed": int(len(t["coupon_redemptions"])),
        "transactions": int(len(t["transactions"])),
        "first_campaign_start": cd["start_date"].min().strftime("%Y-%m-%d"),
        "last_campaign_end": cd["end_date"].max().strftime("%Y-%m-%d"),
        "transactions_start": t["transactions"]["ts"].min().strftime("%Y-%m-%d"),
        "transactions_end": t["transactions"]["ts"].max().strftime("%Y-%m-%d"),
    }


def _coupon_main_department(t: dict) -> pd.DataFrame:
    cp = t["coupons"].merge(t["products"][["product_id", "department"]], on="product_id", how="left")
    return (cp.groupby(["campaign_id", "coupon_upc"])["department"]
              .agg(lambda s: s.value_counts().index[0] if s.notna().any() else "Unknown")
              .rename("department").reset_index())


def campaign_tracker(t: dict, d: pd.DataFrame, train_ids, test_ids) -> list:
    cd = t["campaign_descriptions"].sort_values("start_date")
    red = t["coupon_redemptions"].merge(_coupon_main_department(t), on=["campaign_id", "coupon_upc"], how="left")
    top_dept = red.groupby("campaign_id")["department"].agg(lambda s: s.value_counts().index[0])
    n_coupons = t["coupons"].groupby("campaign_id")["coupon_upc"].nunique()
    agg = d.groupby("campaign_id").agg(households=("household_id", "size"), redeemers=("redeemed", "sum"),
                                       history_days=("history_days", "first"))
    redemptions = t["coupon_redemptions"].groupby("campaign_id").size()
    rows = []
    for c in cd.itertuples(index=False):
        cid = int(c.campaign_id)
        a = agg.loc[cid]
        if cid in test_ids:
            role = "test"
        elif cid in train_ids:
            role = "train"
        elif a["history_days"] < config.MIN_HISTORY_DAYS:
            role = "not used: starts before the purchase data"
        else:
            role = "not used: still running when the test period began"
        rows.append({
            "id": cid, "type": c.campaign_type,
            "start": c.start_date.strftime("%Y-%m-%d"), "end": c.end_date.strftime("%Y-%m-%d"),
            "days": int((c.end_date - c.start_date).days),
            "households": int(a["households"]), "redeemers": int(a["redeemers"]),
            "rate": float(a["redeemers"] / a["households"]),
            "coupons": int(n_coupons.get(cid, 0)), "redemptions": int(redemptions.get(cid, 0)),
            "top_department": str(top_dept.get(cid, "-")).title() if cid in top_dept.index else "-",
            "role": role,
        })
    return rows


def type_summary(d: pd.DataFrame) -> list:
    g = d.groupby("campaign_type").agg(campaigns=("campaign_id", "nunique"), mailings=("redeemed", "size"),
                                       redeemers=("redeemed", "sum"), rate=("redeemed", "mean"))
    return [{"type": k, "campaigns": int(r["campaigns"]), "mailings": int(r["mailings"]),
             "redeemers": int(r["redeemers"]), "rate": float(r["rate"]), "note": TYPE_NOTES[k]}
            for k, r in g.iterrows()]


def signals(d: pd.DataFrame) -> dict:
    h = d[d["has_history"]]
    return {
        "matched_with_coupon": _rate_table(h, "coupons_matched_with_coupon", [-1, 0, 1, 3, np.inf], ["0", "1", "2-3", "4+"]),
        "prior_redemptions": _rate_table(h, "prior_redemptions", [-1, 0, 2, 5, np.inf], ["0", "1-2", "3-5", "6+"]),
        "coupon_habit": _rate_table(h, "coupon_line_rate", [-1, 0, 0.01, 0.03, 1.01], ["Never", "Under 1%", "1-3%", "3%+"]),
        "rows": int(len(h)),
    }


def segments(d: pd.DataFrame) -> dict:
    h = d[d["has_history"]].copy()
    spend_cut = float(h["spend_per_week"].median())
    coupon_cut = float(h["coupon_line_rate"].median())
    big = h["spend_per_week"] > spend_cut
    cpn = h["coupon_line_rate"] > coupon_cut
    h["segment"] = np.select([big & cpn, ~big & cpn, big & ~cpn], ["engaged", "budget", "loyal"], "light")
    meta = {
        "engaged": ("Engaged deal-seekers", "Spend above the median and use coupons more than most"),
        "budget": ("Budget deal-seekers", "Spend below the median but use coupons more than most"),
        "loyal": ("Full-price loyalists", "Spend above the median but rarely use coupons"),
        "light": ("Light shoppers", "Spend below the median and rarely use coupons"),
    }
    out = []
    for key in ["engaged", "budget", "loyal", "light"]:
        s = h[h["segment"] == key]
        out.append({"key": key, "name": meta[key][0], "description": meta[key][1],
                    "n": int(len(s)), "share": float(len(s) / len(h)), "rate": float(s["redeemed"].mean()),
                    "spend_per_week": float(s["spend_per_week"].mean()),
                    "coupon_line_rate": float(s["coupon_line_rate"].mean())})
    return {"segments": out, "spend_cut": spend_cut, "coupon_cut": coupon_cut, "rows": int(len(h))}


def subsidy(t: dict) -> dict:
    """Of the coupons redeemed, how many were for products the household was already buying?"""
    cd = t["campaign_descriptions"]
    cp = t["coupons"][["campaign_id", "coupon_upc", "product_id"]].drop_duplicates()
    min_start = pd.Timestamp(config.DATA_START) + pd.Timedelta(days=config.RECENT_DAYS)
    red = t["coupon_redemptions"].merge(cd[["campaign_id", "campaign_type", "start_date"]], on="campaign_id")
    red = red[red["start_date"] >= min_start]  # need a full 8-week look-back
    key = ["household_id", "campaign_id", "coupon_upc"]
    j = (red.merge(cp, on=["campaign_id", "coupon_upc"])
            .merge(t["transactions"][["household_id", "product_id", "ts"]], on=["household_id", "product_id"]))
    j = j[j["ts"] < j["start_date"]]
    before = j.drop_duplicates(key)[key].assign(before=True)
    recent = j[j["ts"] >= j["start_date"] - pd.Timedelta(days=config.RECENT_DAYS)].drop_duplicates(key)[key].assign(recent=True)
    r = red.merge(before, on=key, how="left").merge(recent, on=key, how="left")
    r[["before", "recent"]] = r[["before", "recent"]].fillna(False).astype(bool)
    breadth = cp.groupby(["campaign_id", "coupon_upc"])["product_id"].nunique().rename("n_products").reset_index()
    r = r.merge(breadth, on=["campaign_id", "coupon_upc"])
    narrow = r[r["n_products"] <= 20]

    def split(s: pd.DataFrame, label: str) -> dict:
        return {"label": label, "n": int(len(s)),
                "recent": float(s["recent"].mean()),
                "earlier": float((s["before"] & ~s["recent"]).mean()),
                "new": float((~s["before"]).mean())}

    groups = [split(r[r["campaign_type"] == "Type A"], "Personalised campaigns (Type A)"),
              split(r[r["campaign_type"] != "Type A"], "Mass campaigns (Types B and C)"),
              split(r, "All campaigns")]
    return {
        "redemptions_checked": int(len(r)),
        "redemptions_total": int(len(t["coupon_redemptions"])),
        "share_bought_before": float(r["before"].mean()),
        "share_bought_recent": float(r["recent"].mean()),
        "narrow_redemptions": int(len(narrow)),
        "narrow_share_bought_before": float(narrow["before"].mean()),
        "narrow_share_bought_recent": float(narrow["recent"].mean()),
        "groups": groups,
    }


def discount_defaults(t: dict, d: pd.DataFrame) -> dict:
    """Average coupon discount on purchases that match a campaign redemption (same household,
    same day, a product the coupon covers, coupon discount > 0)."""
    cp = t["coupons"][["campaign_id", "coupon_upc", "product_id"]].drop_duplicates()
    tx = t["transactions"]
    lines = tx.loc[tx["coupon_disc"] > 0, ["household_id", "product_id", "ts", "coupon_disc"]]
    red = t["coupon_redemptions"]
    lk = red.merge(cp, on=["campaign_id", "coupon_upc"]).merge(lines, on=["household_id", "product_id"])
    lk = lk[lk["ts"].dt.normalize() == lk["redemption_date"]]
    lk = lk.sort_values("coupon_disc", ascending=False).drop_duplicates(["household_id", "campaign_id", "coupon_upc"])
    per_coupon = float(lk["coupon_disc"].mean())
    per_household = float(d.loc[d["redeemed"] == 1, "coupons_redeemed"].mean())
    return {
        "avg_discount_per_coupon": per_coupon,
        "linked_redemptions": int(len(lk)),
        "avg_coupons_per_redeeming_household": per_household,
        "discount_per_redeeming_household": per_coupon * per_household,
    }
