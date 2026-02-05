"""
Configuration for Data Pipeline

This module contains configuration settings for fetching data from MoneyPuck
and Hockey Reference, storing locally for the Streamlit app.
"""

import os
from pathlib import Path

# Base directory (this app's folder)
APP_DIR = Path(__file__).parent.parent

# Output directories (local to this app)
DATA_DIR = APP_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
TEAM_DATA_DIR = RAW_DATA_DIR / "teams"
SKATER_DATA_DIR = RAW_DATA_DIR / "skaters"
GOALIE_DATA_DIR = RAW_DATA_DIR / "goalies"
STANDINGS_DATA_DIR = RAW_DATA_DIR / "standings"

# MoneyPuck API endpoints
MONEYPUCK_BASE_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary"

# Seasons to fetch
# Note: Season year represents the END year (e.g., 2025 = 2024-25 season)
# MoneyPuck only provides current season data now (historical returns 403)
# We only fetch current season; historical data is preserved in the repo
CURRENT_SEASON = 2025  # The 2024-25 season
SEASONS = [CURRENT_SEASON]  # Only fetch current season

# Season types
SEASON_TYPES = ["regular"]  # Can add "playoffs" if needed

# Team name mapping (MoneyPuck abbreviation -> Full name)
TEAM_MAPPING = {
    'ANA': 'Anaheim Ducks',
    'ARI': 'Arizona Coyotes',
    'BOS': 'Boston Bruins',
    'BUF': 'Buffalo Sabres',
    'CAR': 'Carolina Hurricanes',
    'CBJ': 'Columbus Blue Jackets',
    'CGY': 'Calgary Flames',
    'CHI': 'Chicago Blackhawks',
    'COL': 'Colorado Avalanche',
    'DAL': 'Dallas Stars',
    'DET': 'Detroit Red Wings',
    'EDM': 'Edmonton Oilers',
    'FLA': 'Florida Panthers',
    'L.A': 'Los Angeles Kings',
    'LAK': 'Los Angeles Kings',
    'MIN': 'Minnesota Wild',
    'MTL': 'Montreal Canadiens',
    'N.J': 'New Jersey Devils',
    'NJD': 'New Jersey Devils',
    'NSH': 'Nashville Predators',
    'NYI': 'New York Islanders',
    'NYR': 'New York Rangers',
    'OTT': 'Ottawa Senators',
    'PHI': 'Philadelphia Flyers',
    'PIT': 'Pittsburgh Penguins',
    'S.J': 'San Jose Sharks',
    'SJS': 'San Jose Sharks',
    'SEA': 'Seattle Kraken',
    'STL': 'St. Louis Blues',
    'T.B': 'Tampa Bay Lightning',
    'TBL': 'Tampa Bay Lightning',
    'TOR': 'Toronto Maple Leafs',
    'UTA': 'Utah Hockey Club',
    'VAN': 'Vancouver Canucks',
    'VGK': 'Vegas Golden Knights',
    'WPG': 'Winnipeg Jets',
    'WSH': 'Washington Capitals',
}


def ensure_directories():
    """Create output directories if they don't exist"""
    for directory in [DATA_DIR, RAW_DATA_DIR, TEAM_DATA_DIR, SKATER_DATA_DIR, 
                      GOALIE_DATA_DIR, STANDINGS_DATA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
