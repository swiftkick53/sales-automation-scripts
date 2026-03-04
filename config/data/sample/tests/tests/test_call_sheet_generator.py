"""Tests for the call sheet generator."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import tempfile
import os

# Add parent dir to path so we can import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from call_sheet_generator import CallSheetGenerator


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary sample CSV for testing."""
    data = {
        "Prospect_Name": ["Acme Corp", "Beta LLC", "Gamma Inc", "Delta Co"],
        "Rep_Name": ["Alice", "Alice", "Bob", "Bob"],
        "Territory": ["East", "East", "West", "West"],
        "Campaign_Type": [
            "Subscription Winback",
            "Acquisition Winback",
            "Expired with Payment",
            "Subscription Winback",
        ],
        "Last_Contact": [
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
            (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        ],
        "Total_Interactions": [10, 3, 6, 15],
        "Company_Size": [300, 50, 150, 500],
        "Revenue_Potential": [15000, 3000, 8000, 25000],
        "Historical_Conversion_Rate": [0.8, 0.3, 0.6, 0.9],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "test_export.csv"
    df.to_csv(csv_path, index=False)
    return str(csv_path)


@pytest.fixture
def generator(sample_csv):
    """Create a CallSheetGenerator with sample data."""
    return CallSheetGenerator(sample_csv)


class TestCallSheetGenerator:
    """Tests for CallSheetGenerator."""

    def test_load_data(self, generator):
        """Should load all rows from CSV."""
        assert len(generator.df) == 4

    def test_engagement_score_range(self, generator):
        """Engagement scores should be between 0 and 10."""
        for _, row in generator.df.iterrows():
            score = generator.calculate_engagement_score(row)
            assert 0.0 <= score <= 10.0

    def test_ltv_score_range(self, generator):
        """LTV scores should be between 0 and 10."""
        for _, row in generator.df.iterrows():
            score = generator.calculate_ltv_score(row)
            assert 0.0 <= score <= 10.0

    def test_fit_score_known_campaigns(self, generator):
        """Fit scores should return correct values for known campaigns."""
        row_sub = pd.Series({"Campaign_Type": "Subscription Winback"})
        assert generator.calculate_fit_score(row_sub) == 8.0

        row_acq = pd.Series({"Campaign_Type": "Acquisition Winback"})
        assert generator.calculate_fit_score(row_acq) == 6.0

        row_exp = pd.Series({"Campaign_Type": "Expired with Payment"})
        assert generator.calculate_fit_score(row_exp) == 7.0

    def test_tier_assignment(self, generator):
        """Tiers should be 1, 2, or 3."""
        assert generator.assign_tier(8.0) == 1
        assert generator.assign_tier(5.5) == 2
        assert generator.assign_tier(3.0) == 3

    def test_generate_produces_output(self, generator, tmp_path):
        """generate() should return a DataFrame and create a file."""
        os.chdir(tmp_path)
        result = generator.generate(output_format="csv")
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert "Tier" in result.columns
        assert "Combined_Score" in result.columns

    def test_generate_sorted_by_tier(self, generator, tmp_path):
        """Output should be sorted by tier ascending."""
        os.chdir(tmp_path)
        result = generator.generate(output_format="csv")
        tiers = result["Tier"].tolist()
        assert tiers == sorted(tiers)

    def test_recent_contact_scores_higher(self, generator):
        """A prospect contacted yesterday should score higher than 30 days ago."""
        recent = generator.df[
            generator.df["Prospect_Name"] == "Delta Co"
        ].iloc[0]
        stale = generator.df[
            generator.df["Prospect_Name"] == "Beta LLC"
        ].iloc[0]
        assert generator.calculate_engagement_score(recent) > generator.calculate_engagement_score(stale)
