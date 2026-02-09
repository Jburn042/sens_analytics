"""
Fetch data from MoneyPuck.com and Hockey Reference

This script downloads team, skater, and goalie data from MoneyPuck
and standings from Hockey Reference, saving them locally.
"""

import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from io import StringIO
import time
import warnings
from config import (
    MONEYPUCK_BASE_URL,
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
    Fetch team stats (PP%, PK%) from Hockey Reference
    
    Args:
        season: Season year (e.g., 2024 for 2023-24 season)
    
    Returns:
        DataFrame with team PP% and PK%
    """
    from bs4 import Comment
    
    url = f"https://www.hockey-reference.com/leagues/NHL_{season}.html"
    
    print(f"  Fetching team stats for {season}...")
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Hockey Reference hides some tables in HTML comments
        # Search for the stats table in comments
        table = None
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if 'PP%' in comment and 'PK%' in comment:
                comment_soup = BeautifulSoup(comment, 'html.parser')
                table = comment_soup.find('table', {'id': 'stats'})
                if table:
                    break
        
        if table is None:
            print(f"    ✗ Stats table not found")
            return None
        
        df = pd.read_html(StringIO(str(table)))[0]
        
        # Flatten multi-level columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(str(c) for c in col).strip('_') for col in df.columns.values]
        
        # Find team name column and PP%/PK% columns
        team_col = None
        pp_col = None
        pk_col = None
        
        for col in df.columns:
            col_str = str(col)
            # Team name is in the second column (contains 'Unnamed: 1')
            if 'Unnamed: 1_level_0' in col_str and team_col is None:
                team_col = col
            if 'PP%' in col_str and 'Special Teams' in col_str:
                pp_col = col
            if 'PK%' in col_str and 'Special Teams' in col_str:
                pk_col = col
        
        if team_col is None or pp_col is None or pk_col is None:
            print(f"    ✗ Could not find required columns. team={team_col}, pp={pp_col}, pk={pk_col}")
            return None
        
        # Extract relevant columns
        result = pd.DataFrame({
            'team_name': df[team_col].str.replace('*', '', regex=False).str.strip(),  # Remove playoff indicator
            'pp_pct': pd.to_numeric(df[pp_col], errors='coerce') / 100,  # Convert to decimal
            'pk_pct': pd.to_numeric(df[pk_col], errors='coerce') / 100,
            'season': season  # Use same year convention as MoneyPuck (ending year)
        })
        
        # Remove any header rows or averages
        result = result.dropna(subset=['pp_pct', 'pk_pct'])
        # Note: Using word boundaries (\b) to avoid matching 'Lg' in 'Calgary'
        result = result[~result['team_name'].str.contains(r'\bLeague\b|\bAverage\b|\bNHL\b|\bLg\b', case=False, na=False, regex=True)]
        
        print(f"    ✓ {len(result)} teams with PP%/PK%")
        return result
        
    except Exception as e:
        print(f"    ✗ Error fetching team stats: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_standings(season: int) -> pd.DataFrame:
    """
    Fetch team standings from Hockey Reference
    
    Args:
        season: Season year (e.g., 2024 for 2023-24 season)
    
    Returns:
        DataFrame with team standings
    """
    url = f"https://www.hockey-reference.com/leagues/NHL_{season}_standings.html"
    
    print(f"  Fetching standings for {season}...")
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'id': 'expanded_standings'})
        
        if table is None:
            print(f"    ✗ Table not found")
            return None
        
        df = pd.read_html(StringIO(str(table)))[0]
        
        # Extract columns
        keep_cols = []
        if 'Rk' in df.columns:
            keep_cols.append('Rk')
        
        team_col = None
        for col in df.columns:
            if 'Unnamed' in str(col):
                team_col = col
                keep_cols.append(col)
                break
        
        if 'Overall' in df.columns:
            keep_cols.append('Overall')
        
        if keep_cols:
            df = df[keep_cols].copy()
            
            rename_dict = {'Rk': 'team_rank'}
            if team_col:
                rename_dict[team_col] = 'team_name'
            if 'Overall' in df.columns:
                rename_dict['Overall'] = 'record'
            
            df = df.rename(columns=rename_dict)
            
            # Use same year convention as MoneyPuck (ending year, e.g., 2025 for 2024-25 season)
            df['season'] = season
            
            # Parse record
            if 'record' in df.columns:
                def parse_record(record):
                    try:
                        parts = str(record).split('-')
                        return int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
                    except:
                        return 0, 0, 0
                
                parsed = df['record'].apply(parse_record)
                df['wins'] = parsed.apply(lambda x: x[0])
                df['losses'] = parsed.apply(lambda x: x[1])
                df['ot_losses'] = parsed.apply(lambda x: x[2])
                df['points'] = df['wins'] * 2 + df['ot_losses']
            
            print(f"    ✓ {len(df)} teams")
            return df
        
        return None
        
    except Exception as e:
        print(f"    ✗ Error: {e}")
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
    print("\n\n🏆 Hockey Reference Standings")
    print("-" * 40)
    
    all_standings = []
    for season in SEASONS:
        df = fetch_standings(season)
        if df is not None:
            all_standings.append(df)
        time.sleep(1)  # Be nice to the server
    
    if all_standings:
        df_standings = pd.concat(all_standings, ignore_index=True)
        df_standings.to_csv(STANDINGS_DATA_DIR / "team_standings_all_seasons.csv", index=False)
        print(f"\n✓ Saved consolidated standings: {len(df_standings)} rows")
    
    # Fetch team stats (PP%, PK%)
    print("\n\n📈 Hockey Reference Team Stats (PP%, PK%)")
    print("-" * 40)
    
    all_team_stats = []
    for season in SEASONS:
        df = fetch_team_stats(season)
        if df is not None:
            all_team_stats.append(df)
        time.sleep(1)  # Be nice to the server
    
    if all_team_stats:
        df_team_stats = pd.concat(all_team_stats, ignore_index=True)
        df_team_stats.to_csv(STANDINGS_DATA_DIR / "team_stats_all_seasons.csv", index=False)
        print(f"\n✓ Saved team stats: {len(df_team_stats)} rows")
    
    print("\n" + "=" * 60)
    print("DATA FETCH COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    fetch_all()
