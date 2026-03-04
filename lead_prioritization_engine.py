"""
Lead Prioritization Engine — Multi-factor scoring for intelligent prospect ranking.

Combines engagement, LTV potential, and fit into a single priority score,
then identifies "next best actions" for each prospect.

Usage:
    python lead_prioritization_engine.py --data data/processed_master.csv --output output/ranked_leads.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Scoring weights
W_ENGAGEMENT = 0.40
W_LTV = 0.35
W_FIT = 0.25


def score_engagement(row: pd.Series) -> float:
    """Score recency, frequency, and interaction diversity (0-10)."""
    if pd.isna(row.get("Last_Contact")):
        return 0.0

    days_since = (datetime.now() - pd.to_datetime(row["Last_Contact"])).days
    recency = max(0.0, 10.0 - (days_since / 5.0))

    interactions = row.get("Total_Interactions", 0)
    frequency = min(10.0, interactions / 2.0)

    # Interaction diversity bonus (calls + emails + meetings)
    types_present = sum([
        1 for col in ["Calls", "Emails", "Meetings"]
        if row.get(col, 0) > 0
    ])
    diversity_bonus = types_present * 0.5  # max +1.5

    return round(min(10.0, (recency * 0.5) + (frequency * 0.3) + diversity_bonus), 2)


def score_ltv(row: pd.Series) -> float:
    """Score lifetime value potential (0-10)."""
    size = min(10.0, row.get("Company_Size", 0) / 100.0)
    revenue = min(10.0, row.get("Revenue_Potential", 0) / 10000.0)
    history = min(10.0, row.get("Historical_Conversion_Rate", 0) * 10.0)
    return round((size * 0.40) + (revenue * 0.35) + (history * 0.25), 2)


def score_fit(row: pd.Series) -> float:
    """Score prospect-product fit (0-10) based on campaign type and attributes."""
    campaign_map = {
        "Subscription Winback": 8.0,
        "Expired with Payment": 7.0,
        "Acquisition Winback": 6.0,
    }
    base = campaign_map.get(row.get("Campaign_Type", ""), 5.0)

    # Bonus for demonstrated payment history
    if row.get("Revenue_Potential", 0) > 5000:
        base = min(10.0, base + 1.0)

    return round(base, 2)


def suggest_next_action(row: pd.Series) -> str:
    """Recommend next best action based on scoring profile."""
    eng = row.get("Engagement_Score", 0)
    ltv = row.get("LTV_Score", 0)
    days = 999
    if pd.notna(row.get("Last_Contact")):
        days = (datetime.now() - pd.to_datetime(row["Last_Contact"])).days

    if eng >= 7 and ltv >= 7:
        return "Schedule demo / close call"
    elif eng >= 5 and days <= 14:
        return "Follow-up call — warm lead"
    elif ltv >= 7 and eng < 5:
        return "Re-engage: personalized email + value prop"
    elif days > 30:
        return "Winback sequence — email drip"
    else:
        return "Standard outreach call"


def prioritize(input_path: str, output_path: str) -> pd.DataFrame:
    """Score and rank all prospects, suggest next actions."""
    df = pd.read_csv(input_path)
    logger.info("Loaded %d prospects from %s", len(df), input_path)

    df["Engagement_Score"] = df.apply(score_engagement, axis=1)
    df["LTV_Score"] = df.apply(score_ltv, axis=1)
    df["Fit_Score"] = df.apply(score_fit, axis=1)

    df["Priority_Score"] = (
        df["Engagement_Score"] * W_ENGAGEMENT
        + df["LTV_Score"] * W_LTV
        + df["Fit_Score"] * W_FIT
    ).round(2)

    df["Priority_Rank"] = df["Priority_Score"].rank(ascending=False, method="dense").astype(int)
    df["Next_Action"] = df.apply(suggest_next_action, axis=1)

    df = df.sort_values("Priority_Rank")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info("Saved ranked leads -> %s", output_path)

    # Summary
    print(f"\n{'='*55}")
    print(f"  LEAD PRIORITIZATION SUMMARY")
    print(f"{'='*55}")
    print(f"  Total leads scored : {len(df)}")
    print(f"  Avg priority score : {df['Priority_Score'].mean():.2f}")
    print(f"\n  Top 10 prospects:")
    top = df.head(10)
    for _, r in top.iterrows():
        name = r.get("Prospect_Name", r.get("Account_Name", "Unknown"))
        print(f"    #{r['Priority_Rank']:<3d} {name:<25s} "
              f"Score: {r['Priority_Score']:.2f}  → {r['Next_Action']}")
    print(f"{'='*55}\n")

    return df


def main():
    parser = argparse.ArgumentParser(description="Rank and prioritize leads.")
    parser.add_argument("--data", required=True, help="Processed master CSV")
    parser.add_argument("--output", default="output/ranked_leads.csv")
    args = parser.parse_args()
    prioritize(args.data, args.output)


if __name__ == "__main__":
    main()
