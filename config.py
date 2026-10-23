"""Settings shared by every step of the pipeline.

Change values here, then run `python run_pipeline.py` to rebuild the dashboard data.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SITE_DATA_FILE = ROOT / "site" / "assets" / "data.js"

# 84.51° Complete Journey data, as packaged in the `completejourney` R package (CC0 licence).
SOURCE_URL = "https://raw.githubusercontent.com/bradleyboehmke/completejourney/master/data/"
SOURCE_FILES = {
    "campaigns": "campaigns.rda",
    "campaign_descriptions": "campaign_descriptions.rda",
    "coupons": "coupons.rda",
    "coupon_redemptions": "coupon_redemptions.rda",
    "demographics": "demographics.rda",
    "products": "products.rda",
    "transactions": "transactions.rds",
}

# Transactions start on this date, so a campaign needs some history before it starts.
DATA_START = "2017-01-01"
MIN_HISTORY_DAYS = 28          # campaigns starting earlier than 4 weeks into the data are left out of the model
RECENT_DAYS = 56               # "recent" window = last 8 weeks before a campaign starts

# Time-based test: train on campaigns that had finished before this date,
# test on campaigns that started on or after it (like the AmExpert winners' "last campaigns" validation).
TEST_START = "2017-10-01"

RANDOM_SEED = 42
BOOTSTRAP_REPS = 1000
