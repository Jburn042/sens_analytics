"""
Data Loader for Sens Analytics App

This module loads processed data from the local data/ folder.
"""

import pandas as pd
from pathlib import Path

# Data directory (relative to this file)
DATA_DIR = Path(__file__).parent / "data"


def load_team_season_metrics() -> pd.DataFrame:
    """
    Load team season metrics data
    
    Returns:
        DataFrame with team-level metrics joined with standings
    """
    file_path = DATA_DIR / "team_season_metrics.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Team season metrics file not found: {file_path}\n"
            "Run the data pipeline first: python pipeline/fetch_data.py && python pipeline/process_data.py"
        )
    
    df = pd.read_csv(file_path)
    print(f"Loaded team season metrics: {len(df)} rows, {df['season'].nunique()} seasons")
    return df


def load_player_data(season: int = None) -> pd.DataFrame:
    """
    Load player data (5on5 only - for analytical metrics)
    
    Args:
        season: Optional season to filter to. If None, loads all seasons.
    
    Returns:
        DataFrame with player statistics
    """
    file_path = DATA_DIR / "player_data.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Player data file not found: {file_path}\n"
            "Run the data pipeline first."
        )
    
    df = pd.read_csv(file_path)
    
    if season is not None:
        df = df[df['season'] == season].copy()
        print(f"Loaded player data for {season}: {len(df)} players")
    else:
        print(f"Loaded player data: {len(df)} players across {df['season'].nunique()} seasons")
    
    return df


def load_player_data_all(season: int = None) -> pd.DataFrame:
    """
    Load player data (all situations - for total stats like GP, Points, Goals)
    
    Args:
        season: Optional season to filter to. If None, loads all seasons.
    
    Returns:
        DataFrame with player total statistics
    """
    file_path = DATA_DIR / "player_data_all.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Player data (all situations) file not found: {file_path}\n"
            "Run the data pipeline first."
        )
    
    df = pd.read_csv(file_path)
    
    if season is not None:
        df = df[df['season'] == season].copy()
        print(f"Loaded player data (all) for {season}: {len(df)} players")
    else:
        print(f"Loaded player data (all): {len(df)} players across {df['season'].nunique()} seasons")
    
    return df


def load_goalie_data(season: int = None) -> pd.DataFrame:
    """
    Load goalie data (team-level, 5on5 only)
    
    Args:
        season: Optional season to filter to. If None, loads all seasons.
    
    Returns:
        DataFrame with goalie metrics by team
    """
    file_path = DATA_DIR / "goalie_data.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Goalie data file not found: {file_path}\n"
            "Run the data pipeline first."
        )
    
    df = pd.read_csv(file_path)
    
    if season is not None:
        df = df[df['season'] == season].copy()
        print(f"Loaded goalie data for {season}: {len(df)} teams")
    else:
        print(f"Loaded goalie data: {len(df)} teams across {df['season'].nunique()} seasons")
    
    return df


def check_data_availability() -> dict:
    """
    Check which data files are available
    
    Returns:
        Dict with availability status for each file type
    """
    availability = {
        'team_season_metrics': (DATA_DIR / "team_season_metrics.csv").exists(),
        'player_data': (DATA_DIR / "player_data.csv").exists(),
        'goalie_data': (DATA_DIR / "goalie_data.csv").exists(),
        'data_dir': DATA_DIR.exists()
    }
    
    return availability


def get_data_last_updated() -> str:
    """Get the timestamp of when data was last refreshed by the pipeline"""
    from datetime import datetime, timezone, timedelta
    
    timestamp_file = DATA_DIR / "last_updated.txt"
    if timestamp_file.exists():
        utc_str = timestamp_file.read_text().strip()
        try:
            utc_dt = datetime.fromisoformat(utc_str)
            et = timezone(timedelta(hours=-5))
            et_dt = utc_dt.astimezone(et)
            return et_dt.strftime('%b %d, %Y at %-I:%M %p') + " EST"
        except ValueError:
            pass
    
    file_path = DATA_DIR / "team_season_metrics.csv"
    if file_path.exists():
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    
    return "Unknown"
