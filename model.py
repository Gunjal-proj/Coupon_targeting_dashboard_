"""Step 3 - who should get the campaign? Random vs a simple rule vs machine-learning models.

Evaluation mirrors how a marketer would use the scores: for each new campaign, rank the households
it was going to be sent to, mail only the top X%, and count how many of the eventual redeemers
that reaches. Everything is measured on later campaigns the models never saw.
"""
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import config
from .features import MODEL_FEATURES

DEPTHS = np.linspace(0, 1, 101)  # 0%, 1%, ..., 100% of households mailed

LGB_PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_child_samples=40,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                  random_state=config.RANDOM_SEED, verbose=-1)

SKEWED = ["spend_per_week", "baskets_per_week", "avg_basket_value", "days_since_last_visit",
          "recent_spend_per_week", "spend_trend", "n_departments", "prior_campaigns_received",
          "prior_campaigns_redeemed", "prior_redemptions", "coupons_matched", "coupons_matched_with_coupon",
          "coupon_products_bought", "coupon_product_spend_per_week", "n_coupons", "campaign_days"]


# ---------------------------------------------------------------- split & scores
def split(d: pd.DataFrame):
    """Train on campaigns that had ended before TEST_START; test on campaigns starting on/after it."""
    test_start = pd.Timestamp(config.TEST_START)
    usable = d[d["has_history"]]
    test = usable[usable["start_date"] >= test_start].copy()
    first_test_start = test["start_date"].min()
    train = usable[usable["end_date"] < first_test_start].copy()
    return train, test


def rule_score(df: pd.DataFrame) -> np.ndarray:
    """AmExpert Rank-2 style rule, no model: rank by matching products bought with a coupon,
    then matching products bought at all, then past redemption rate."""
    return (df["coupons_matched_with_coupon"].to_numpy() * 1e6
            + df["coupons_matched"].clip(upper=999).to_numpy() * 1e3
            + df["prior_redeem_rate"].to_numpy())


def make_logistic() -> Pipeline:
    other = [f for f in MODEL_FEATURES if f not in SKEWED]
    prep = ColumnTransformer([
        ("skewed", Pipeline([("imp", SimpleImputer(strategy="median")),
                             ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one"))]), SKEWED),
        ("other", SimpleImputer(strategy="median", add_indicator=True), other),
    ])
    return Pipeline([("prep", prep), ("scale", StandardScaler()),
                     ("lr", LogisticRegression(C=0.5, max_iter=5000))])


# ---------------------------------------------------------------- evaluation helpers
def _campaign_gains(scores: np.ndarray, y: np.ndarray, depths: np.ndarray) -> np.ndarray:
    """Expected number of redeemers reached when mailing the top d% (ties broken at random)."""
    n = len(y)
    order = np.argsort(-scores, kind="mergesort")
    s, yy = scores[order], y[order]
    _, starts, sizes = np.unique(-s, return_index=True, return_counts=True)
    group_pos = np.add.reduceat(yy, starts)
    cum_n = np.concatenate([[0], np.cumsum(sizes)])
    cum_p = np.concatenate([[0], np.cumsum(group_pos)])
    k = depths * n
    g = np.clip(np.searchsorted(cum_n, k, side="right") - 1, 0, len(sizes) - 1)
    frac = np.clip((k - cum_n[g]) / sizes[g], 0, 1)
    return cum_p[g] + frac * group_pos[g]


def gains_curve(df: pd.DataFrame, scores: np.ndarray, depths: np.ndarray = DEPTHS) -> np.ndarray:
    """Share of all redeemers reached at each depth, ranking households within each campaign."""
    reached = np.zeros(len(depths))
    total = 0
    for _, idx in df.groupby("campaign_id").indices.items():
        y = df["redeemed"].to_numpy()[idx]
        reached += _campaign_gains(scores[idx], y, depths)
        total += y.sum()
    return reached / total


def weighted_auc(df: pd.DataFrame, scores: np.ndarray) -> float:
    """AUC within each campaign, averaged with weights = number of redeemers."""
    num = den = 0.0
    y_all = df["redeemed"].to_numpy()
    for _, idx in df.groupby("campaign_id").indices.items():
        y = y_all[idx]
        if 0 < y.sum() < len(y):
            num += roc_auc_score(y, scores[idx]) * y.sum()
            den += y.sum()
    return num / den


def _fit_lgb(X, y, n_rounds):
    return lgb.LGBMClassifier(n_estimators=n_rounds, **LGB_PARAMS).fit(X, y)


def choose_lgb_rounds(train: pd.DataFrame) -> int:
    folds = list(GroupKFold(n_splits=5).split(train, groups=train["campaign_id"]))
    ds = lgb.Dataset(train[MODEL_FEATURES], train["redeemed"])
    cv = lgb.cv({**LGB_PARAMS, "metric": "auc"}, ds, num_boost_round=1500, folds=folds,
                callbacks=[lgb.early_stopping(100, verbose=False)], seed=config.RANDOM_SEED)
    return len(cv["valid auc-mean"])


def cv_compare(train: pd.DataFrame, n_rounds: int) -> dict:
    """Within-campaign AUC on held-out campaigns inside the training period (used to pick the model)."""
    out = {"rule": [], "logistic": [], "lightgbm": []}
    for tr_idx, va_idx in GroupKFold(n_splits=5).split(train, groups=train["campaign_id"]):
        tr, va = train.iloc[tr_idx], train.iloc[va_idx]
        out["rule"].append(weighted_auc(va, rule_score(va)))
        lr = make_logistic().fit(tr[MODEL_FEATURES], tr["redeemed"])
        out["logistic"].append(weighted_auc(va, lr.predict_proba(va[MODEL_FEATURES])[:, 1]))
        gb = _fit_lgb(tr[MODEL_FEATURES], tr["redeemed"], n_rounds)
        out["lightgbm"].append(weighted_auc(va, gb.predict_proba(va[MODEL_FEATURES])[:, 1]))
    return {k: float(np.mean(v)) for k, v in out.items()}


def bootstrap(test: pd.DataFrame, scores: dict, depth: float = 0.3, reps: int = config.BOOTSTRAP_REPS) -> dict:
    """95% intervals for 'share of redeemers reached at depth' and AUC, resampling households within campaigns."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    groups = list(test.groupby("campaign_id").indices.values())
    names = list(scores)
    res = {n: {"reach": [], "auc": []} for n in names}
    diff = {"reach": [], "auc": []}
    for _ in range(reps):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        b = test.iloc[idx].reset_index(drop=True)
        vals = {}
        for n in names:
            s = scores[n][idx]
            r = float(gains_curve(b, s, np.array([depth]))[0])
            a = weighted_auc(b, s)
            res[n]["reach"].append(r)
            res[n]["auc"].append(a)
            vals[n] = (r, a)
        diff["reach"].append(vals["model"][0] - vals["rule"][0])
        diff["auc"].append(vals["model"][1] - vals["rule"][1])
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    out = {n: {"reach_ci": ci(res[n]["reach"]), "auc_ci": ci(res[n]["auc"])} for n in names}
    out["model_minus_rule"] = {"reach_ci": ci(diff["reach"]), "auc_ci": ci(diff["auc"]),
                               "share_reps_model_better_reach": float(np.mean(np.array(diff["reach"]) > 0))}
    return out


FEATURE_GROUPS = {
    "Already buys the coupon products": ["coupons_matched", "coupons_matched_share", "coupons_matched_with_coupon",
                                         "coupon_products_bought", "coupon_product_spend_per_week"],
    "Has redeemed campaign coupons before": ["prior_campaigns_received", "prior_campaigns_redeemed",
                                             "prior_redemptions", "prior_redeem_rate"],
    "Coupon and deal habits": ["coupon_line_rate", "coupon_savings_share", "promo_line_rate", "private_label_share"],
    "Shopping level and trend": ["spend_per_week", "baskets_per_week", "avg_basket_value", "days_since_last_visit",
                                 "recent_spend_per_week", "spend_trend", "n_departments"],
    "Demographics": ["age_rank", "income_rank", "household_size", "kids_count"],
}


def permutation_importance(model, test: pd.DataFrame, groups: dict, repeats: int = 10) -> pd.Series:
    """Drop in within-campaign AUC when a column (or group of columns) is shuffled within each campaign."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    X = test[MODEL_FEATURES].reset_index(drop=True)
    t = test.reset_index(drop=True)
    base = weighted_auc(t, model.predict_proba(X)[:, 1])
    camp_idx = list(t.groupby("campaign_id").indices.values())
    drops = {}
    for name, cols in groups.items():
        vals = []
        for _ in range(repeats):
            Xp = X.copy()
            for g in camp_idx:  # shuffle the whole group of columns together, keeping rows aligned
                perm = rng.permutation(g)
                Xp.loc[g, cols] = X.loc[perm, cols].to_numpy()
            vals.append(base - weighted_auc(t, model.predict_proba(Xp)[:, 1]))
        drops[name] = float(np.mean(vals))
    return pd.Series(drops).sort_values(ascending=False)


# ---------------------------------------------------------------- main entry
def run(d: pd.DataFrame) -> dict:
    train, test = split(d)
    test = test.reset_index(drop=True)
    n_rounds = choose_lgb_rounds(train)
    cv = cv_compare(train, n_rounds)

    lr = make_logistic().fit(train[MODEL_FEATURES], train["redeemed"])
    gb = _fit_lgb(train[MODEL_FEATURES], train["redeemed"], n_rounds)
    best_name = "lightgbm" if cv["lightgbm"] >= cv["logistic"] else "logistic"
    best = gb if best_name == "lightgbm" else lr

    scores = {
        "rule": rule_score(test),
        "logistic": lr.predict_proba(test[MODEL_FEATURES])[:, 1],
        "lightgbm": gb.predict_proba(test[MODEL_FEATURES])[:, 1],
    }
    scores["model"] = scores[best_name]
    test["model_score"] = scores["model"]
    test["rule_score"] = scores["rule"]

    curves = {k: gains_curve(test, v) for k, v in scores.items()}
    curves["random"] = DEPTHS.copy()
    aucs = {k: weighted_auc(test, v) for k, v in scores.items()}
    boot = bootstrap(test, {"model": scores["model"], "rule": scores["rule"]})
    importance_groups = permutation_importance(best, test, FEATURE_GROUPS)
    importance_features = permutation_importance(best, test, {f: [f] for f in MODEL_FEATURES}, repeats=5)

    # Results split by campaign type (personalised Type A vs mass Types B/C)
    by_type = {}
    for label, mask in [("personalised", test["campaign_type"] == "Type A"),
                        ("mass", test["campaign_type"] != "Type A")]:
        sub = test[mask]
        by_type[label] = {
            "households": int(len(sub)), "redeemers": int(sub["redeemed"].sum()),
            "campaigns": sorted(int(c) for c in sub["campaign_id"].unique()),
            "reach30_model": float(gains_curve(sub, sub["model_score"].to_numpy(), np.array([0.3]))[0]),
            "reach30_rule": float(gains_curve(sub, sub["rule_score"].to_numpy(), np.array([0.3]))[0]),
            "auc_model": weighted_auc(sub, sub["model_score"].to_numpy()),
            "auc_rule": weighted_auc(sub, sub["rule_score"].to_numpy()),
        }

    # Who the model puts in its top 20% (within each campaign) vs everyone else
    test["model_rank_pct"] = test.groupby("campaign_id")["model_score"].rank(ascending=False, pct=True, method="first")
    test["top20"] = test["model_rank_pct"] <= 0.2

    return {
        "train": train, "test": test, "n_rounds": n_rounds, "cv_auc": cv, "best_name": best_name,
        "curves": curves, "auc": aucs, "bootstrap": boot, "importance_groups": importance_groups,
        "importance_features": importance_features, "by_type": by_type, "lr_model": lr, "lgb_model": gb,
    }
