"""Step 5 - write the numbers the dashboard needs into site/assets/data.js (and a copy in data/processed/)."""
import json
import re
from datetime import date

import numpy as np

from . import config
from .model import DEPTHS

FEATURE_LABELS = {
    "coupons_matched": "Campaign coupons matching products they already buy",
    "coupons_matched_share": "Share of the campaign's coupons matching past purchases",
    "coupons_matched_with_coupon": "Matching products they once bought with a coupon",
    "coupon_products_bought": "Campaign coupon products they have bought",
    "coupon_product_spend_per_week": "Weekly spend on the campaign's coupon products",
    "prior_campaigns_received": "Past campaigns received",
    "prior_campaigns_redeemed": "Past campaigns redeemed",
    "prior_redemptions": "Past coupons redeemed",
    "prior_redeem_rate": "Past redemption rate",
    "coupon_line_rate": "Share of items bought with a coupon",
    "coupon_savings_share": "Coupon savings as a share of spend",
    "promo_line_rate": "Share of items bought on promotion",
    "private_label_share": "Private-label share of spend",
    "spend_per_week": "Weekly spend",
    "baskets_per_week": "Shopping trips per week",
    "avg_basket_value": "Average basket value",
    "days_since_last_visit": "Days since last visit",
    "recent_spend_per_week": "Weekly spend, last 8 weeks",
    "spend_trend": "Spend trend (last 8 weeks vs before)",
    "n_departments": "Departments shopped",
    "is_type_a": "Personalised campaign",
    "n_coupons": "Coupons in the campaign",
    "campaign_days": "Campaign length",
    "age_rank": "Age band",
    "income_rank": "Income band",
    "household_size": "Household size",
    "kids_count": "Number of children",
}


def _r(x, n=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def _curve(a):
    return [round(float(v), 4) for v in a]


def _clean(o):
    """Round floats and convert numpy types so the JSON stays small and valid."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return _r(o)
    return o


def build_payload(t, d, m, ins) -> dict:
    test, train = m["test"], m["train"]
    curves = m["curves"]
    reach = lambda k, p: float(curves[k][int(p)])
    top = test[test["top20"]]
    rest = test[~test["top20"]]

    def profile(s):
        return {"households": int(len(s)), "rate": float(s["redeemed"].mean()),
                "has_redeemed_before": float((s["prior_campaigns_redeemed"] > 0).mean()),
                "matched_with_coupon": float(s["coupons_matched_with_coupon"].mean()),
                "coupon_line_rate": float(s["coupon_line_rate"].mean()),
                "spend_per_week": float(s["spend_per_week"].mean())}

    ig = m["importance_groups"].clip(lower=0)
    imp_feat = m["importance_features"].clip(lower=0)
    disc = ins["discount"]
    payload = {
        "meta": {
            "generated": date.today().isoformat(),
            "source": "84.51° Complete Journey (via the completejourney R package)",
            "source_url": "https://github.com/bradleyboehmke/completejourney",
            "licence": "CC0 1.0 (public domain)",
            "inspired_by": "AmExpert 2019 Machine Learning Hackathon (American Express x Analytics Vidhya)",
            "inspired_by_url": "https://www.analyticsvidhya.com/blog/2019/10/5-winning-solutions-approaches-amexpert-retail_hackathon-feature-engineering/",
            "winners_repo_url": "https://github.com/kunalj101/amExpert_ML_Hackathon_2019_Winners_Soultions",
            "test_start": config.TEST_START,
            "min_history_days": config.MIN_HISTORY_DAYS,
        },
        "kpis": ins["kpis"],
        "campaigns": ins["campaigns"],
        "types": ins["types"],
        "signals": ins["signals"],
        "segments": ins["segments"],
        "subsidy": ins["subsidy"],
        "model": {
            "chosen": m["best_name"],
            "chosen_label": "LightGBM (gradient-boosted trees)" if m["best_name"] == "lightgbm" else "Logistic regression",
            "lgb_rounds": int(m["n_rounds"]),
            "cv_auc": m["cv_auc"],
            "test_auc": {k: float(v) for k, v in m["auc"].items()},
            "train_campaigns": sorted(int(c) for c in train["campaign_id"].unique()),
            "test_campaigns": sorted(int(c) for c in test["campaign_id"].unique()),
            "train_households": int(len(train)), "train_redeemers": int(train["redeemed"].sum()),
            "test_households": int(len(test)), "test_redeemers": int(test["redeemed"].sum()),
            "base_rate": float(test["redeemed"].mean()),
            "depths": _curve(DEPTHS),
            "curves": {k: _curve(curves[k]) for k in ["random", "rule", "model", "logistic", "lightgbm"]},
            "reach": {k: {str(p): reach(k, p) for p in (10, 20, 30, 50)} for k in ["rule", "model", "logistic", "lightgbm"]},
            "bootstrap": m["bootstrap"],
            "by_type": m["by_type"],
            "importance_groups": [{"name": k, "auc_drop": float(v), "relative": float(v / ig.max())} for k, v in ig.items()],
            "importance_features": [{"feature": k, "label": FEATURE_LABELS.get(k, k), "auc_drop": float(v)}
                                    for k, v in imp_feat.head(10).items()],
            "top20": profile(top), "rest": profile(rest),
        },
        "simulator": {
            "defaults": {"audience": 10000, "send_cost": 0.50,
                         "discount": round(disc["discount_per_redeeming_household"], 2),
                         "extra_profit": 12.0, "incremental": 0.5},
            "discount_basis": disc,
        },
    }
    return _clean(payload)


def write(payload: dict) -> None:
    config.SITE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    config.SITE_DATA_FILE.write_text(
        "// Generated by run_pipeline.py - do not edit by hand.\n"
        f"window.DASHBOARD_DATA = {body};\n", encoding="utf-8")
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (config.PROCESSED_DIR / "dashboard_data.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                                               encoding="utf-8")


def update_readme(payload: dict) -> None:
    """Refresh the numbers between the RESULTS markers in README.md."""
    readme = config.ROOT / "README.md"
    if not readme.exists():
        return
    m, k = payload["model"], payload["kpis"]
    pct = lambda x: f"{x * 100:.1f}%"
    b = m["bootstrap"]
    block = "\n".join([
        "<!-- RESULTS:START (auto-generated by run_pipeline.py) -->",
        "| What | Result |",
        "|---|---|",
        f"| Campaign mailings that led to no redemption | **{pct(k['no_redemption_share'])}** of {k['mailings']:,} |",
        f"| Redeemers reached by mailing the top 30% (later campaigns, never seen in training) | Model **{pct(m['reach']['model']['30'])}** (95% CI {pct(b['model']['reach_ci'][0])}-{pct(b['model']['reach_ci'][1])}) · Simple rule {pct(m['reach']['rule']['30'])} · Random 30.0% |",
        f"| Ranking quality (within-campaign AUC) | Model {m['test_auc']['model']:.3f} · Logistic regression {m['test_auc']['logistic']:.3f} · Simple rule {m['test_auc']['rule']:.3f} |",
        f"| Redemption rate, model's top 20% vs the rest | **{pct(m['top20']['rate'])}** vs {pct(m['rest']['rate'])} |",
        f"| Redemptions on products the household had already bought | **{pct(payload['subsidy']['share_bought_before'])}** |",
        "<!-- RESULTS:END -->",
    ])
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"<!-- RESULTS:START.*?<!-- RESULTS:END -->", block, text, flags=re.S)
    readme.write_text(text, encoding="utf-8")
