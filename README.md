# Sens Friendly Analytics App

A Streamlit-based NHL analytics tool for team performance prediction, player comparison, and trade simulation.

## Features

- **Team Analysis**: Predicted vs actual standings with performance radar charts
- **Player Comparison**: Compare players across seasons with percentile rankings
- **Trade Simulator**: Simulate trades and see impact on team metrics and rankings

---

## Architecture Overview

### Data Sources

| Source | Data Provided | Update Speed |
|--------|--------------|------------|
| **MoneyPuck** | Player stats, team metrics (5on5, all situations) | ~7 AM EST daily |
| **NHL API** | Standings, PP%, PK% | Minutes after game completion |

Both sources use the **START year** convention (2025 = 2025-26 season). The NHL API uses `seasonId` format `20252026`.

### Data Flow

```
MoneyPuck API ────┐
                  ├──► fetch_data.py ──► data/raw/ ──► process_data.py ──► data/*.csv
NHL API (JSON) ───┘
```

### Season Convention

Throughout this codebase, seasons use the **START year** (MoneyPuck convention):
- `season = 2025` means the 2025-26 NHL season
- This is set in `pipeline/config.py` as `CURRENT_SEASON = 2025`

---

## Daily Data Updates

### GitHub Actions Workflow

Location: `.github/workflows/daily_data_update.yml`

**Triggers:**
1. `schedule`: Cron at 11:30 UTC (6:30 AM EST / 7:30 AM EDT) - backup, unreliable on GitHub
2. `workflow_dispatch`: Manual trigger from GitHub Actions UI
3. `repository_dispatch`: External API trigger (recommended for reliability)

**Recommended Setup**: Use [cron-job.org](https://cron-job.org) to call the GitHub API daily:
```
URL: https://api.github.com/repos/Jburn042/sens_analytics/dispatches
Method: POST
Headers:
  Authorization: Bearer <GITHUB_PAT>
  Accept: application/vnd.github.v3+json
Body: {"event_type": "daily-update"}
```

### Keeping Streamlit App Awake

Streamlit Community Cloud apps sleep after inactivity. Set up a second cron job to ping the app URL periodically (every few hours). The ping registers activity even with password protection.

---

## Model Details

### StandingsModel (`standings_model.py`)

- **Algorithm**: RandomForestRegressor
- **Target**: `team_rank` (1-32)
- **Features**: `net_flurry_xgoals`, `corsipercentage`, `pp_pct`, `pk_pct`, etc.
- **Training Data**: Historical seasons (2019-2024) from `team_season_metrics.csv`

### RosterSimulator (`roster_simulation.py`)

- Calculates player contributions to team metrics using per-minute rates
- Simulates trades by swapping player contributions between teams
- Re-predicts standings using the trained model

**Known Limitation**: Uses 5on5 data only, which undervalues players with high power play impact (e.g., star offensive players). The model measures possession/defense contribution, not raw offensive production.

---

## Standings Rankings

Rankings in `team_season_metrics.csv` are calculated as:
1. **Primary sort**: Points percentage (descending)
2. **Tiebreaker**: Regulation wins (descending)

This matches NHL.com's "P%" sorted standings view, which is more accurate mid-season when teams have played different numbers of games.

Both `pointPctg` and `regulationWins` come directly from the NHL API — no manual calculation required.

---

## File Structure

```
sens_analytics/
├── app.py                    # Main Streamlit application
├── auth.py                   # Password authentication
├── standings_model.py        # Team standings prediction model
├── roster_simulation.py      # Trade simulation logic
├── load_data.py              # Data loading utilities
├── requirements.txt          # Python dependencies
├── .streamlit/
│   └── secrets.toml.example  # Template for local secrets
├── data/                     # Processed data files (auto-updated daily)
│   ├── team_season_metrics.csv   # Team stats + standings (model training data)
│   ├── player_data.csv           # Player 5on5 stats
│   ├── player_data_all.csv       # Player all-situations stats
│   └── goalie_data.csv           # Goalie metrics
├── data/raw/                 # Raw fetched data (gitignored, regenerated)
│   ├── teams/
│   ├── skaters/
│   ├── goalies/
│   └── standings/
├── pipeline/
│   ├── config.py             # CURRENT_SEASON, team mappings
│   ├── fetch_data.py         # Fetches from MoneyPuck + NHL API
│   └── process_data.py       # Transforms raw → processed CSVs
└── .github/workflows/
    └── daily_data_update.yml # Automated data refresh
```

---

## Key Configuration

### `pipeline/config.py`

```python
CURRENT_SEASON = 2025  # The 2025-26 season (start year)
SEASONS = [CURRENT_SEASON]  # Only fetch current season
```

**Why only current season?** MoneyPuck API returns 403 Forbidden for historical seasons. Historical data is preserved in the repo and merged with fresh current-season data.

### Data Preservation (`process_data.py`)

The `merge_with_existing()` function:
1. Loads existing CSV (contains historical + previous current season data)
2. Removes only CURRENT_SEASON rows from existing data
3. Appends fresh CURRENT_SEASON data
4. Saves combined result

This preserves historical data while updating only the current season.

---

## Common Issues & Solutions

### "Team data not found for [year]"
- Check `CURRENT_SEASON` in `config.py`
- Verify NHL API `seasonId` format is `{season}{season+1}` (e.g., `20252026`)
- Run pipeline locally: `cd pipeline && python fetch_data.py && python process_data.py`

### Missing PP%/PK% data
- Check NHL API endpoints: `api.nhle.com/stats/rest/en/team/powerplay` and `.../penaltykill`
- Verify `seasonId` parameter matches current season

### GitHub Actions push fails
1. Check repository Settings → Actions → General → "Read and write permissions"
2. The workflow uses `stefanzweifel/git-auto-commit-action@v5` which handles merge conflicts

### Streamlit app shows stale data
1. Reboot app: Streamlit Cloud → your app → ⋮ menu → Reboot app
2. This clears `@st.cache_resource` cached model

### Model gives illogical trade results
- Small sample size players have inflated per-minute stats
- Model uses 5on5 metrics only; star players' PP impact is invisible
- This is a known limitation, not a bug

---

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run data pipeline
cd pipeline
python fetch_data.py
python process_data.py

# Run app
cd ..
streamlit run app.py
```

### Local Secrets

Create `.streamlit/secrets.toml`:
```toml
[auth]
password = "your-password"
```

---

## Updating the App

### Adding New Metrics

1. Add metric calculation to `pipeline/process_data.py`
2. Add metric name to `standings_model.py` → `metrics_list`
3. Add metric name to `roster_simulation.py` → `metrics_list`
4. Add display name to `app.py` → `METRIC_DISPLAY_NAMES`

### New Season Rollover

When a new season starts (e.g., 2026-27):
1. Update `CURRENT_SEASON = 2026` in `pipeline/config.py`
2. The pipeline will automatically fetch new season data
3. Previous season data becomes part of historical training data

---

## Security Notes

- Password stored in Streamlit Cloud Secrets (not in repo)
- `.streamlit/secrets.toml` is gitignored
- Repo is public; no sensitive data should be committed
- GitHub PAT for cron triggers should have minimal scope (repo dispatch only)

---

## Contact

Built by Jamie Burns for Sens Friendly analytics.
