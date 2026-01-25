# Sens Friendly Analytics App

A Streamlit-based NHL analytics tool for team performance prediction, player comparison, and trade simulation.

## Features

- **Team Analysis**: Predicted vs actual standings with performance radar charts
- **Player Comparison**: Compare players across seasons with percentile rankings
- **Trade Simulator**: Simulate trades and see impact on team metrics and rankings


## Daily Data Updates (Already Configured)

A GitHub Actions workflow runs automatically every day at 6 AM ET to:
- Fetch latest player and team stats from MoneyPuck
- Fetch standings and PP/PK data from Hockey-Reference  
- Update the CSV files in `data/`
- Commit changes to the repository

Streamlit Cloud automatically picks up new commits, so your app will always show fresh data.

**Manual trigger**: Go to GitHub → Actions → "Daily Data Update" → "Run workflow"

---

## File Structure

```
sens_analytics_app_jb/
├── app.py                 # Main Streamlit application
├── standings_model.py     # Team standings prediction model
├── roster_simulation.py   # Trade simulation logic
├── load_data.py          # Data loading utilities
├── requirements.txt      # Python dependencies
├── .streamlit/
│   └── secrets.toml      # Local secrets (not committed)
├── data/                  # Processed data files (auto-updated)
│   ├── team_season_metrics.csv
│   ├── player_data.csv
│   ├── player_data_all.csv
│   └── goalie_data.csv
└── pipeline/             # Data fetching scripts
    ├── fetch_data.py
    └── process_data.py
```

---

## Updating the App

### Adding New Metrics

1. Add metric calculation to `pipeline/process_data.py`
2. Add metric name to `standings_model.py` → `metrics_list`
3. Add metric name to `roster_simulation.py` → `metrics_list`  
4. Add display name to `app.py` → `METRIC_DISPLAY_NAMES`

### New Season (e.g., 2026)

The app automatically handles new seasons. When MoneyPuck publishes 2026 data, it will appear in the app after the next daily data update.

---

## Troubleshooting

**App shows old data**: 
- Wait for the daily update (6 AM ET) or manually trigger the GitHub Action

**Deployment fails**:
- Check that `requirements.txt` is in the app directory
- Verify the main file path is correct

**Password not working**:
- Check Secrets in Streamlit Cloud settings
- Make sure format is exactly `[auth]` then `password = "your-password"`

---

## Contact

Built by Jamie Burns for Sens Friendly analytics.
