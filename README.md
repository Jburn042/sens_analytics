# Sens Friendly Analytics App

A Streamlit-based NHL analytics tool for team performance prediction, player comparison, and trade simulation.

## Features

- **Team Analysis**: Predicted vs actual standings with performance radar charts
- **Player Comparison**: Compare players across seasons with percentile rankings
- **Trade Simulator**: Simulate trades and see impact on team metrics and rankings

## Quick Start (Local Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Access at `http://localhost:8501`

---

## Deployment to Streamlit Cloud (Step-by-Step)

### Step 1: Commit Your Code

Make sure all your changes are committed and pushed to GitHub:

```bash
git add -A
git commit -m "Ready for deployment"
git push origin your-branch-name
```

### Step 2: Create Streamlit Cloud Account

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "Sign in with GitHub"
3. Authorize Streamlit to access your GitHub

### Step 3: Deploy the App

1. Click **"New app"** button
2. Fill in the form:
   - **Repository**: `Fullscript/sens_friendly`
   - **Branch**: `20251115_jamie_afternoon_sensfriendly` (or your branch)
   - **Main file path**: `sens_analytics/sens_analytics_app_jb/app.py`
3. Click **"Deploy!"**

### Step 4: Configure Password (Secrets)

1. In Streamlit Cloud, go to your app's **Settings** (gear icon)
2. Click **"Secrets"** in the left sidebar
3. Paste the following:

```toml
[auth]
password = "50in07"
```

4. Click **"Save"**

### Step 5: Share Your App

Your app will be available at a URL like:
```
https://your-app-name.streamlit.app
```

Share this URL + the password with anyone who needs access.

---

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
