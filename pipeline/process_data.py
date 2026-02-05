"""
Process raw data into analysis-ready CSVs

This script reads raw MoneyPuck data and standings, processes them,
and creates the final CSV files used by the Streamlit app.
"""

import pandas as pd
from pathlib import Path
from config import (
    DATA_DIR,
    TEAM_DATA_DIR,
    SKATER_DATA_DIR,
    STANDINGS_DATA_DIR,
    TEAM_MAPPING,
    CURRENT_SEASON,
    ensure_directories
)


def load_and_concat_csvs(directory: Path) -> pd.DataFrame:
    """Load all CSV files from a directory and concatenate them"""
    csv_files = list(directory.glob("*.csv"))
    
    if not csv_files:
        print(f"  Warning: No CSV files in {directory}")
        return pd.DataFrame()
    
    dfs = [pd.read_csv(f) for f in csv_files]
    df_combined = pd.concat(dfs, ignore_index=True)
    print(f"  Loaded {len(csv_files)} files, {len(df_combined)} total rows")
    
    return df_combined


def merge_with_existing(new_data: pd.DataFrame, existing_file: Path, 
                        season_col: str = 'season') -> pd.DataFrame:
    """
    Merge new data with existing data, replacing only current season rows.
    This preserves historical data while updating the current season.
    """
    if not existing_file.exists():
        print(f"  No existing file, using new data only")
        return new_data
    
    existing_data = pd.read_csv(existing_file)
    print(f"  Loaded existing data: {len(existing_data)} rows, seasons: {sorted(existing_data[season_col].unique())}")
    
    # Remove current season from existing data (we'll replace with new)
    historical_data = existing_data[existing_data[season_col] != CURRENT_SEASON]
    print(f"  Historical data (preserved): {len(historical_data)} rows")
    
    # Get current season from new data
    current_season_data = new_data[new_data[season_col] == CURRENT_SEASON]
    print(f"  Current season data (new): {len(current_season_data)} rows")
    
    # Combine historical + new current season
    merged = pd.concat([historical_data, current_season_data], ignore_index=True)
    print(f"  Merged total: {len(merged)} rows")
    
    return merged


def create_team_season_metrics():
    """
    Create team_season_metrics.csv by joining teams data with standings
    
    This replicates the SQL query in ws_team_season_metrics.sql
    """
    print("\n📊 Creating Team Season Metrics")
    print("-" * 40)
    
    # Load team data (all situations)
    df_teams_all = load_and_concat_csvs(TEAM_DATA_DIR)
    
    if df_teams_all.empty:
        print("  ✗ No team data found")
        return
    
    # Load real PP% and PK% from Hockey Reference
    team_stats_file = STANDINGS_DATA_DIR / "team_stats_all_seasons.csv"
    if team_stats_file.exists():
        df_team_stats = pd.read_csv(team_stats_file)
        print(f"  Loaded team stats (PP%, PK%): {len(df_team_stats)} rows")
    else:
        print("  ⚠ Team stats file not found - PP%/PK% will be missing")
        df_team_stats = pd.DataFrame()
    
    # Filter to 5on5 situations for core metrics
    df_teams = df_teams_all[df_teams_all['situation'] == '5on5'].copy()
    print(f"  Filtered to 5on5: {len(df_teams)} rows")
    
    # Map team abbreviations to full names
    df_teams['team_full'] = df_teams['team'].map(TEAM_MAPPING)
    
    # Load standings
    standings_file = STANDINGS_DATA_DIR / "team_standings_all_seasons.csv"
    if not standings_file.exists():
        print(f"  ✗ Standings file not found: {standings_file}")
        return
    
    df_standings = pd.read_csv(standings_file)
    print(f"  Loaded standings: {len(df_standings)} rows")
    
    # Join with standings
    df_final = df_teams.merge(
        df_standings[['team_name', 'season', 'team_rank', 'points']],
        left_on=['team_full', 'season'],
        right_on=['team_name', 'season'],
        how='left'
    )
    
    # Calculate derived metrics (matching the SQL query exactly)
    df_final['net_flurry_xgoals'] = (
        df_final['flurryScoreVenueAdjustedxGoalsFor'] - 
        df_final['flurryScoreVenueAdjustedxGoalsAgainst']
    )
    df_final['actual_goal_differential'] = df_final['goalsFor'] - df_final['goalsAgainst']
    df_final['penalty_differential'] = df_final['penaltiesFor'] - df_final['penaltiesAgainst']
    df_final['net_takeaways'] = df_final['takeawaysFor'] - df_final['takeawaysAgainst']
    df_final['shooting_percentage'] = df_final['goalsFor'] / df_final['shotsOnGoalFor']
    df_final['save_percentage'] = df_final['savedShotsOnGoalAgainst'] / df_final['shotsOnGoalAgainst']
    df_final['net_score_adjusted_shots'] = (
        df_final['scoreAdjustedShotsAttemptsFor'] - 
        df_final['scoreAdjustedShotsAttemptsAgainst']
    )
    df_final['net_high_danger_shots'] = df_final['highDangerShotsFor'] - df_final['highDangerShotsAgainst']
    df_final['goals_saved_above_expected'] = df_final['xGoalsAgainst'] - df_final['goalsAgainst']
    df_final['net_high_danger_xgoals'] = (
        df_final['highDangerxGoalsFor'] - 
        df_final['highDangerxGoalsAgainst']
    )
    
    # Merge in real PP% and PK% from Hockey Reference
    if not df_team_stats.empty:
        df_final = df_final.merge(
            df_team_stats[['team_name', 'season', 'pp_pct', 'pk_pct']],
            left_on=['team_full', 'season'],
            right_on=['team_name', 'season'],
            how='left'
        )
        print(f"  Added real PP% and PK% metrics")
    else:
        df_final['pp_pct'] = None
        df_final['pk_pct'] = None
    
    # Select final columns
    output_cols = [
        'team_full',
        'season',
        'team_rank',
        'points',
        'net_flurry_xgoals',
        'actual_goal_differential',
        'penalty_differential',
        'net_takeaways',
        'corsiPercentage',
        'shooting_percentage',
        'save_percentage',
        'net_score_adjusted_shots',
        'net_high_danger_shots',
        'goals_saved_above_expected',
        'net_high_danger_xgoals',
        'pp_pct',
        'pk_pct'
    ]
    
    # Filter to rows with valid standings data
    df_output = df_final[output_cols].dropna(subset=['team_rank'])
    
    # Normalize column name
    df_output = df_output.rename(columns={'corsiPercentage': 'corsipercentage'})
    
    # Merge with existing historical data
    output_file = DATA_DIR / "team_season_metrics.csv"
    df_output = merge_with_existing(df_output, output_file, season_col='season')
    
    # Sort and save
    df_output = df_output.sort_values(['team_full', 'season'])
    df_output.to_csv(output_file, index=False)
    
    print(f"  ✓ Created: team_season_metrics.csv")
    print(f"    Rows: {len(df_output)}")
    print(f"    Seasons: {sorted(df_output['season'].unique())}")
    print(f"    Teams: {df_output['team_full'].nunique()}")


def create_player_data():
    """Create consolidated player_data.csv with all seasons"""
    print("\n👤 Creating Player Data")
    print("-" * 40)
    
    df_skaters = load_and_concat_csvs(SKATER_DATA_DIR)
    
    if df_skaters.empty:
        print("  ✗ No skater data found")
        return
    
    # Create all-situations data (for total stats display)
    df_all = df_skaters[df_skaters['situation'] == 'all'].copy()
    df_all = df_all.sort_values(['season', 'team', 'name'])
    
    all_output_file = DATA_DIR / "player_data_all.csv"
    df_all = merge_with_existing(df_all, all_output_file, season_col='season')
    df_all = df_all.sort_values(['season', 'team', 'name'])
    df_all.to_csv(all_output_file, index=False)
    print(f"  ✓ Created: player_data_all.csv ({len(df_all)} rows)")
    
    # Create 5on5 data (for analytical metrics)
    df_5on5 = df_skaters[df_skaters['situation'] == '5on5'].copy()
    df_5on5 = df_5on5.sort_values(['season', 'team', 'name'])
    
    output_file = DATA_DIR / "player_data.csv"
    df_5on5 = merge_with_existing(df_5on5, output_file, season_col='season')
    df_5on5 = df_5on5.sort_values(['season', 'team', 'name'])
    df_5on5.to_csv(output_file, index=False)
    
    print(f"  ✓ Created: player_data.csv (5on5 only)")
    print(f"    Total players: {len(df_5on5)}")


def create_goalie_data():
    """Create goalie_data.csv with team-level goalie metrics"""
    print("\n🥅 Creating Goalie Data")
    print("-" * 40)
    
    df_teams = load_and_concat_csvs(TEAM_DATA_DIR)
    
    if df_teams.empty:
        print("  ✗ No team data found")
        return
    
    # Filter to 5on5
    df_teams = df_teams[df_teams['situation'] == '5on5'].copy()
    
    # Map team names
    df_teams['team_full'] = df_teams['team'].map(TEAM_MAPPING)
    
    # Select goalie-relevant metrics
    goalie_cols = ['team_full', 'season']
    
    # Add available goalie columns
    for col in ['goalsAgainst', 'xGoalsAgainst', 'shotsOnGoalAgainst', 
                'savedShotsOnGoalAgainst', 'highDangerShotsAgainst', 'highDangerxGoalsAgainst']:
        if col in df_teams.columns:
            goalie_cols.append(col)
    
    df_goalies = df_teams[goalie_cols].copy()
    
    # Calculate save percentage and GSAX
    if 'savedShotsOnGoalAgainst' in df_goalies.columns and 'shotsOnGoalAgainst' in df_goalies.columns:
        df_goalies['save_percentage'] = df_goalies['savedShotsOnGoalAgainst'] / df_goalies['shotsOnGoalAgainst']
    
    if 'xGoalsAgainst' in df_goalies.columns and 'goalsAgainst' in df_goalies.columns:
        df_goalies['goals_saved_above_expected'] = df_goalies['xGoalsAgainst'] - df_goalies['goalsAgainst']
    
    # Rename for consistency
    df_goalies = df_goalies.rename(columns={'team_full': 'team'})
    
    # Merge with existing historical data
    output_file = DATA_DIR / "goalie_data.csv"
    # Rename 'team' column temporarily for merge (it's 'team' in goalie data, not 'team_full')
    df_goalies = merge_with_existing(df_goalies, output_file, season_col='season')
    
    # Sort and save
    df_goalies = df_goalies.sort_values(['season', 'team'])
    df_goalies.to_csv(output_file, index=False)
    
    print(f"  ✓ Created: goalie_data.csv")
    print(f"    Total rows: {len(df_goalies)}")


def process_all():
    """Run all data processing"""
    ensure_directories()
    
    print("=" * 60)
    print("PROCESSING NHL DATA")
    print("=" * 60)
    
    create_team_season_metrics()
    create_player_data()
    create_goalie_data()
    
    print("\n" + "=" * 60)
    print("DATA PROCESSING COMPLETE!")
    print("=" * 60)
    print(f"\nOutput files in: {DATA_DIR}")


if __name__ == "__main__":
    process_all()
