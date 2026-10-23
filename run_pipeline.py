"""Run the whole analysis and rebuild the dashboard data.

    pip install -r requirements.txt
    python run_pipeline.py

Takes about two minutes. Output: site/assets/data.js (what the dashboard reads) and
data/processed/dashboard_data.json (same numbers, readable).
"""
import time

from pipeline import config, export, features, get_data, insights, model


def main() -> None:
    t0 = time.time()
    step = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}")

    step("1/5 Downloading 84.51° Complete Journey data (skipped if already in data/raw/)")
    get_data.download()
    tables = get_data.load()

    step("2/5 Building one row per household x campaign (pre-campaign history only)")
    d = features.build(tables)

    step("3/5 Training and testing: random vs simple rule vs models")
    m = model.run(d)

    step("4/5 Marketing insights")
    train_ids = set(m["train"]["campaign_id"].unique())
    test_ids = set(m["test"]["campaign_id"].unique())
    ins = {
        "kpis": insights.kpis(tables, d),
        "campaigns": insights.campaign_tracker(tables, d, train_ids, test_ids),
        "types": insights.type_summary(d),
        "signals": insights.signals(d),
        "segments": insights.segments(d),
        "subsidy": insights.subsidy(tables),
        "discount": insights.discount_defaults(tables, d),
    }

    step("5/5 Writing site/assets/data.js")
    payload = export.build_payload(tables, d, m, ins)
    export.write(payload)
    export.update_readme(payload)
    # test-set scores, so anyone can re-check the headline numbers without retraining
    m["test"][["campaign_id", "household_id", "campaign_type", "redeemed", "model_score", "rule_score"]].to_csv(
        config.PROCESSED_DIR / "test_scores.csv", index=False)

    mm = payload["model"]
    step(f"Done. Mailing the model's top 30% reaches {mm['reach']['model']['30']:.1%} of redeemers "
         f"(simple rule {mm['reach']['rule']['30']:.1%}, random 30%).")


if __name__ == "__main__":
    main()
