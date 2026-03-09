"""
Fetch data from MoneyPuck.com and NHL API

This script downloads team, skater, and goalie data from MoneyPuck
and standings/team stats from the NHL API, saving them locally.
"""

import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import StringIO
import time
import unicodedata
import warnings
from config import (
    MONEYPUCK_BASE_URL,
    DATA_DIR,
    TEAM_DATA_DIR,
    SKATER_DATA_DIR,
    GOALIE_DATA_DIR,
    STANDINGS_DATA_DIR,
    SEASONS,
    SEASON_TYPES,
    ensure_directories
)

# Suppress SSL warnings for corporate proxy environments
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
try:
    from urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
except ImportError:
    pass


def normalize_team_name(name: str) -> str:
    """Normalize unicode characters in team names (e.g. Montréal -> Montreal)"""
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def fetch_moneypuck_data(data_type: str, season: int, season_type: str = "regular") -> pd.DataFrame:
    """
    Fetch data from MoneyPuck API
    
    Args:
        data_type: One of 'teams', 'skaters', 'goalies'
        season: Season year (e.g., 2024)
        season_type: 'regular' or 'playoffs'
    
    Returns:
        DataFrame with the fetched data
    """
    url = f"{MONEYPUCK_BASE_URL}/{season}/{season_type}/{data_type}.csv"
    
    print(f"  Fetching {data_type} for {season}...")
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text))
        df['season'] = season
        df['season_type'] = season_type
        
        # Clean column names
        df.columns = [
            col.replace(' ', '_')
               .replace('(', '_')
               .replace(')', '_')
               .replace('.', '_')
            for col in df.columns
        ]
        
        print(f"    ✓ {len(df)} rows")
        return df
        
    except requests.exceptions.HTTPError as e:
        print(f"    ✗ HTTP Error: {e}")
        return None
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


def fetch_team_stats(season: int) -> pd.DataFrame:
    """
    Fetch team stats (PP%, PK%) from NHL API
    
    Args:
        season: Season START year (e.g., 2025 for 2025-26 season) - matches MoneyPuck convention
    
    Returns:
        DataFrame with team PP% and PK%
    """
    season_id = f"{season}{season + 1}"
    
    pp_url = f"https://api.nhle.com/stats/rest/en/team/powerplay?cayenneExp=seasonId={season_id}"
    pk_url = f"https://api.nhle.com/stats/rest/en/team/penaltykill?cayenneExp=seasonId={season_id}"
    
    print(f"  Fetching team stats for {season} (NHL API seasonId {season_id})...")
    
    try:
        pp_resp = requests.get(pp_url, timeout=30)
        pp_resp.raise_for_status()
        pp_data = pp_resp.json()['data']
        
        pk_resp = requests.get(pk_url, timeout=30)
        pk_resp.raise_for_status()
        pk_data = pk_resp.json()['data']
        
        pp_df = pd.DataFrame([{
            'team_name': normalize_team_name(t['teamFullName']),
            'pp_pct': t['powerPlayPct'],
        } for t in pp_data])
        
        pk_df = pd.DataFrame([{
            'team_name': normalize_team_name(t['teamFullName']),
            'pk_pct': t['penaltyKillPct'],
        } for t in pk_data])
        
        result = pp_df.merge(pk_df, on='team_name', how='outer')
        result['season'] = season
        
        print(f"    ✓ {len(result)} teams with PP%/PK%")
        return result
        
    except Exception as e:
        print(f"    ✗ Error fetching team stats: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_standings(season: int) -> pd.DataFrame:
    """
    Fetch team standings from NHL API
    
    Args:
        season: Season START year (e.g., 2025 for 2025-26 season) - matches MoneyPuck convention
    
    Returns:
        DataFrame with team standings
    """
    url = "https://api-web.nhle.com/v1/standings/now"
    
    print(f"  Fetching standings for {season} (NHL API)...")
    
    try:
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        data = response.json()
        standings = data['standings']
        
        target_season_id = int(f"{season}{season + 1}")
        standings = [t for t in standings if t['seasonId'] == target_season_id]
        
        if not standings:
            print(f"    ✗ No standings found for seasonId {target_season_id}")
            return None
        
        rows = []
        for t in standings:
            rows.append({
                'team_name': normalize_team_name(t['teamName']['default']),
                'season': season,
                'wins': t['wins'],
                'losses': t['losses'],
                'ot_losses': t['otLosses'],
                'points': t['points'],
                'regulation_wins': t['regulationWins'],
                'games_played': t['gamesPlayed'],
                'pts_pct': t['pointPctg'],
                'record': f"{t['wins']}-{t['losses']}-{t['otLosses']}",
            })
        
        df = pd.DataFrame(rows)
        
        # Rank by P% (primary), regulation wins as tiebreaker (secondary)
        df = df.sort_values(['pts_pct', 'regulation_wins'], ascending=[False, False]).reset_index(drop=True)
        df['team_rank'] = df.index + 1
        
        print(f"    ✓ {len(df)} teams")
        return df
        
    except Exception as e:
        print(f"    ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_all():
    """Fetch all data from MoneyPuck and Hockey Reference"""
    ensure_directories()
    
    print("=" * 60)
    print("FETCHING NHL DATA")
    print("=" * 60)
    
    # Fetch MoneyPuck data
    print("\n📊 MoneyPuck Data")
    print("-" * 40)
    
    for data_type, output_dir in [('teams', TEAM_DATA_DIR), 
                                   ('skaters', SKATER_DATA_DIR), 
                                   ('goalies', GOALIE_DATA_DIR)]:
        print(f"\n{data_type.upper()}:")
        for season in SEASONS:
            for season_type in SEASON_TYPES:
                df = fetch_moneypuck_data(data_type, season, season_type)
                
                if df is not None and not df.empty:
                    filename = f"{data_type}_{season}_{season_type}.csv"
                    df.to_csv(output_dir / filename, index=False)
                
                time.sleep(0.5)  # Be nice to the server
    
    # Fetch standings
    print("\n\n🏆 NHL API Standings")
    print("-" * 40)
    
    all_standings = []
    for season in SEASONS:
        df = fetch_standings(season)
        if df is not None:
            all_standings.append(df)
        time.sleep(0.5)
    
    if all_standings:
        df_standings = pd.concat(all_standings, ignore_index=True)
        df_standings.to_csv(STANDINGS_DATA_DIR / "team_standings_all_seasons.csv", index=False)
        print(f"\n✓ Saved consolidated standings: {len(df_standings)} rows")
    
    # Fetch team stats (PP%, PK%)
    print("\n\n📈 NHL API Team Stats (PP%, PK%)")
    print("-" * 40)
    
    all_team_stats = []
    for season in SEASONS:
        df = fetch_team_stats(season)
        if df is not None:
            all_team_stats.append(df)
        time.sleep(0.5)
    
    if all_team_stats:
        df_team_stats = pd.concat(all_team_stats, ignore_index=True)
        df_team_stats.to_csv(STANDINGS_DATA_DIR / "team_stats_all_seasons.csv", index=False)
        print(f"\n✓ Saved team stats: {len(df_team_stats)} rows")
    
    # Write timestamp so the app knows when data was last refreshed
    now_utc = datetime.now(timezone.utc)
    est = timezone(timedelta(hours=-5))
    edt = timezone(timedelta(hours=-4))
    now_est = now_utc.astimezone(est)
    now_edt = now_utc.astimezone(edt)
    
    timestamp_file = DATA_DIR / "last_updated.txt"
    timestamp_file.write_text(now_utc.isoformat())
    print(f"\n✓ Wrote timestamp: {now_utc.isoformat()}")
    
    print("\n" + "=" * 60)
    print("DATA FETCH COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    fetch_all()
