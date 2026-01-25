"""
Roster Simulation Module - Trade Impact Analysis

Simulate trades and analyze impact on team performance.
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from load_data import load_player_data, load_goalie_data, load_team_season_metrics
from standings_model import StandingsModel


class RosterSimulator:
    """Simulate trades and analyze impact on team performance"""
    
    # Mapping from team abbreviations to full team names
    TEAM_ABBREV_TO_FULL = {
        'ANA': 'Anaheim Ducks',
        'ARI': 'Arizona Coyotes',
        'BOS': 'Boston Bruins',
        'BUF': 'Buffalo Sabres',
        'CGY': 'Calgary Flames',
        'CAR': 'Carolina Hurricanes',
        'CHI': 'Chicago Blackhawks',
        'COL': 'Colorado Avalanche',
        'CBJ': 'Columbus Blue Jackets',
        'DAL': 'Dallas Stars',
        'DET': 'Detroit Red Wings',
        'EDM': 'Edmonton Oilers',
        'FLA': 'Florida Panthers',
        'L.A': 'Los Angeles Kings',
        'LAK': 'Los Angeles Kings',
        'MIN': 'Minnesota Wild',
        'MTL': 'Montreal Canadiens',
        'NSH': 'Nashville Predators',
        'N.J': 'New Jersey Devils',
        'NJD': 'New Jersey Devils',
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
        'WSH': 'Washington Capitals',
        'WPG': 'Winnipeg Jets',
    }
    
    def __init__(self, season=2025, standings_model=None):
        self.metrics_list = [
            'net_flurry_xgoals',
            'net_score_adjusted_shots',
            'corsipercentage',
            'save_percentage',
            'net_high_danger_shots',
            'goals_saved_above_expected',
            'net_high_danger_xgoals',
            'shooting_percentage'
        ]
        
        self.goalie_metrics = ['save_percentage', 'goals_saved_above_expected']
        self.current_season = season  # Season for team rankings
        
        # Load ALL player data (all seasons)
        df_players_all = load_player_data(season=None)  # Load all seasons
        self.player_data_all = self._deduplicate_players_by_season(df_players_all)
        
        # For backward compatibility, also keep current season data
        self.player_data = self.player_data_all[self.player_data_all['season'] == season].copy()
        
        # Load goalie and team data
        self.goalie_data = load_goalie_data(season=None)  # All seasons
        self.team_data = load_team_season_metrics()
        
        # Available seasons
        self.available_seasons = sorted(self.player_data_all['season'].unique(), reverse=True)
        
        # Use the same StandingsModel for consistent predictions
        if standings_model is not None:
            self.standings_model = standings_model
        else:
            self.standings_model = StandingsModel()
        
        # Use the standings model's trained model
        self.model = self.standings_model.model
        
        # Calculate scaling factors to align roster-calculated metrics with team-level data
        self.metric_scaling_factors = self._calculate_scaling_factors()
    
    def _deduplicate_players_by_season(self, df):
        """Deduplicate by keeping highest ice time entry per player per team per season"""
        df_dedup = df.sort_values('icetime', ascending=False).groupby(['season', 'team', 'name'], as_index=False).first()
        print(f"Loaded {len(df_dedup)} unique player-seasons")
        return df_dedup
    
    def get_players_for_season(self, season):
        """Get all players for a specific season"""
        return self.player_data_all[self.player_data_all['season'] == season].copy()
    
    def get_teams_for_season(self, season):
        """Get all teams for a specific season"""
        season_data = self.player_data_all[self.player_data_all['season'] == season]
        return sorted(season_data['team'].unique())
    
    def _get_full_team_name(self, team_abbrev):
        """Convert team abbreviation to full team name for matching with team_season_metrics"""
        return self.TEAM_ABBREV_TO_FULL.get(team_abbrev, team_abbrev)
    

    def _calculate_scaling_factors(self):
        """
        Calculate scaling factors to convert roster-level metrics to team-level metrics.
        This aligns the calculated metrics with what the model was trained on.
        """
        scaling_factors = {}
        current_players = self.player_data_all[self.player_data_all['season'] == self.current_season]
        current_team_data = self.team_data[self.team_data['season'] == self.current_season]
        
        # For each team, compare calculated vs actual metrics
        ratios = {metric: [] for metric in self.metrics_list if metric not in self.goalie_metrics}
        
        for team in current_players['team'].unique():
            team_roster = current_players[current_players['team'] == team]
            calculated = self._calculate_raw_roster_metrics(team_roster)
            
            if calculated is None:
                continue
            
            # Convert abbreviation to full team name for matching
            team_full = self._get_full_team_name(team)
            actual_row = current_team_data[current_team_data['team_full'] == team_full]
            if len(actual_row) == 0:
                continue
            actual = actual_row.iloc[0]
            
            for metric in ratios.keys():
                if metric in calculated and calculated[metric] != 0:
                    ratio = actual[metric] / calculated[metric]
                    if 0.1 < ratio < 100:  # Sanity check
                        ratios[metric].append(ratio)
        
        # Use median ratio as scaling factor
        for metric in ratios.keys():
            if ratios[metric]:
                scaling_factors[metric] = np.median(ratios[metric])
            else:
                scaling_factors[metric] = 1.0
        
        # Goalie metrics don't need scaling
        for metric in self.goalie_metrics:
            scaling_factors[metric] = 1.0
            
        print(f"Calculated scaling factors for roster metrics")
        return scaling_factors
    
    def _calculate_metric_percentiles(self, metrics):
        """Calculate percentiles for metrics relative to current season teams"""
        from scipy import stats
        
        # Get all teams for current season
        season_data = self.team_data[self.team_data['season'] == self.current_season]
        
        percentiles = {}
        for metric in self.metrics_list:
            if metric in metrics:
                metric_values = season_data[metric].values
                value = metrics[metric]
                percentile = stats.percentileofscore(metric_values, value)
                percentiles[metric] = percentile
        
        return percentiles
    
    def get_team_roster(self, team):
        """Get current roster for a team"""
        roster = self.player_data[self.player_data['team'] == team].copy()
        return roster.sort_values('icetime', ascending=False)
    
    def get_all_teams(self):
        """Get list of all teams"""
        return sorted(self.player_data['team'].unique())
    
    def find_player(self, player_name, team=None):
        """Find player(s) by name"""
        if team:
            matches = self.player_data[
                (self.player_data['name'].str.contains(player_name, case=False, na=False)) &
                (self.player_data['team'] == team)
            ]
        else:
            matches = self.player_data[
                self.player_data['name'].str.contains(player_name, case=False, na=False)
            ]
        return matches.sort_values('icetime', ascending=False)
    
    def _calculate_raw_roster_metrics(self, roster):
        """Calculate raw (unscaled) team metrics from roster - used for calibration"""
        if len(roster) == 0:
            return None
        
        total_icetime = roster['icetime'].sum()
        if total_icetime == 0:
            return None
            
        weights = roster['icetime'].values / total_icetime
        
        metrics = {}
        
        def safe_weighted_avg(col_for, col_against=None, default=0):
            try:
                if col_for in roster.columns:
                    vals_for = roster[col_for].fillna(0).values
                    if col_against and col_against in roster.columns:
                        vals_against = roster[col_against].fillna(0).values
                        return np.average(vals_for - vals_against, weights=weights)
                    return np.average(vals_for, weights=weights)
            except:
                pass
            return default
        
        metrics['net_flurry_xgoals'] = safe_weighted_avg(
            'OnIce_F_flurryScoreVenueAdjustedxGoals',
            'OnIce_A_flurryScoreVenueAdjustedxGoals'
        )
        metrics['net_score_adjusted_shots'] = safe_weighted_avg(
            'OnIce_F_scoreAdjustedShotsAttempts',
            'OnIce_A_scoreAdjustedShotsAttempts'
        )
        metrics['net_high_danger_shots'] = safe_weighted_avg(
            'OnIce_F_highDangerShots',
            'OnIce_A_highDangerShots'
        )
        metrics['net_high_danger_xgoals'] = safe_weighted_avg(
            'OnIce_F_highDangerxGoals',
            'OnIce_A_highDangerxGoals'
        )
        
        if 'onIce_corsiPercentage' in roster.columns:
            metrics['corsipercentage'] = safe_weighted_avg('onIce_corsiPercentage', default=0.5)
        else:
            shots_for = safe_weighted_avg('OnIce_F_shotAttempts', default=50)
            shots_against = safe_weighted_avg('OnIce_A_shotAttempts', default=50)
            metrics['corsipercentage'] = shots_for / (shots_for + shots_against) if (shots_for + shots_against) > 0 else 0.5
        
        total_goals = roster['I_F_goals'].fillna(0).sum() if 'I_F_goals' in roster.columns else 0
        total_shots = roster['I_F_shotsOnGoal'].fillna(0).sum() if 'I_F_shotsOnGoal' in roster.columns else 1
        metrics['shooting_percentage'] = total_goals / total_shots if total_shots > 0 else 0.08
        
        return metrics
    
    def calculate_team_metrics_from_roster(self, roster, team_goalie_metrics=None):
        """Calculate team-level metrics from roster, scaled to match model training data"""
        raw_metrics = self._calculate_raw_roster_metrics(roster)
        
        if raw_metrics is None:
            return None
        
        # Apply scaling factors to align with team-level data
        metrics = {}
        for metric in raw_metrics:
            if metric in self.metric_scaling_factors:
                metrics[metric] = raw_metrics[metric] * self.metric_scaling_factors[metric]
            else:
                metrics[metric] = raw_metrics[metric]
        
        # Goalie metrics (don't change with skater trades)
        if team_goalie_metrics:
            metrics['save_percentage'] = team_goalie_metrics['save_percentage']
            metrics['goals_saved_above_expected'] = team_goalie_metrics['goals_saved_above_expected']
        else:
            metrics['save_percentage'] = 0.910
            metrics['goals_saved_above_expected'] = 0.0
        
        return metrics
    
    def calculate_trade_impact(self, team, player_out, player_in):
        """
        Calculate the impact of swapping one player for another on a team's metrics.
        Uses actual team data as baseline and calculates delta from player swap.
        
        Returns modified team metrics.
        """
        # Get actual team metrics as baseline
        team_full = self._get_full_team_name(team)
        team_actual = self.team_data[
            (self.team_data['season'] == self.current_season) & 
            (self.team_data['team_full'] == team_full)
        ]
        
        if len(team_actual) == 0:
            return None
            
        baseline_metrics = {m: team_actual.iloc[0][m] for m in self.metrics_list}
        
        # Calculate player contribution differences (ice-time weighted)
        roster = self.player_data_all[
            (self.player_data_all['season'] == self.current_season) & 
            (self.player_data_all['team'] == team)
        ]
        
        if len(roster) == 0:
            return baseline_metrics
            
        total_icetime = roster['icetime'].sum()
        
        # Player out weight
        out_icetime = player_out['icetime'] if 'icetime' in player_out else 0
        out_weight = out_icetime / total_icetime if total_icetime > 0 else 0
        
        # Player in weight (assume they take similar ice time as player out)
        in_weight = out_weight
        
        # Calculate impact on each metric
        modified_metrics = baseline_metrics.copy()
        
        metric_columns = {
            'net_flurry_xgoals': ('OnIce_F_flurryScoreVenueAdjustedxGoals', 'OnIce_A_flurryScoreVenueAdjustedxGoals'),
            'net_score_adjusted_shots': ('OnIce_F_scoreAdjustedShotsAttempts', 'OnIce_A_scoreAdjustedShotsAttempts'),
            'net_high_danger_shots': ('OnIce_F_highDangerShots', 'OnIce_A_highDangerShots'),
            'net_high_danger_xgoals': ('OnIce_F_highDangerxGoals', 'OnIce_A_highDangerxGoals'),
        }
        
        for metric, (col_for, col_against) in metric_columns.items():
            if col_for in player_out.index and col_for in player_in.index:
                # Calculate per-minute rates
                out_rate = (player_out[col_for] - player_out[col_against]) / out_icetime if out_icetime > 0 else 0
                in_rate = (player_in[col_for] - player_in[col_against]) / player_in['icetime'] if player_in['icetime'] > 0 else 0
                
                # Scale to season impact (using out player's ice time as basis)
                rate_diff = in_rate - out_rate
                # Scale appropriately - use scaling factors
                if metric in self.metric_scaling_factors:
                    impact = rate_diff * out_icetime * self.metric_scaling_factors[metric]
                else:
                    impact = rate_diff * out_icetime
                
                modified_metrics[metric] = baseline_metrics[metric] + impact
        
        # Corsi percentage - weighted average change
        if 'onIce_corsiPercentage' in player_out.index and 'onIce_corsiPercentage' in player_in.index:
            corsi_diff = (player_in['onIce_corsiPercentage'] - player_out['onIce_corsiPercentage']) * out_weight
            modified_metrics['corsipercentage'] = baseline_metrics['corsipercentage'] + corsi_diff
        
        # Shooting percentage change
        if 'I_F_goals' in player_out.index and 'I_F_shotsOnGoal' in player_out.index:
            out_sh = player_out['I_F_goals'] / player_out['I_F_shotsOnGoal'] if player_out['I_F_shotsOnGoal'] > 0 else 0.08
            in_sh = player_in['I_F_goals'] / player_in['I_F_shotsOnGoal'] if player_in['I_F_shotsOnGoal'] > 0 else 0.08
            sh_diff = (in_sh - out_sh) * out_weight
            modified_metrics['shooting_percentage'] = baseline_metrics['shooting_percentage'] + sh_diff
        
        return modified_metrics
    
    def predict_team_rank(self, team_metrics):
        """Predict team rank from metrics"""
        if team_metrics is None:
            return None
        
        metrics_df = pd.DataFrame([team_metrics])
        prediction = self.model.predict(metrics_df[self.metrics_list])[0]
        return max(1, min(32, round(prediction)))
    
    def get_team_predicted_rank(self, team, season=None):
        """Get the precomputed predicted rank for a team from the standings model"""
        if season is None:
            season = self.current_season
        
        # Convert abbreviation to full team name
        team_full = self._get_full_team_name(team)
        
        # Use standings model's precomputed ranks for consistency
        team_result = self.standings_model.df_results[
            (self.standings_model.df_results['season'] == season) &
            (self.standings_model.df_results['team_full'] == team_full)
        ]
        
        if len(team_result) > 0:
            return int(team_result.iloc[0]['predicted_rank_placement'])
        return None
    
    def simulate_trade(self, team_a, player_a_name, team_b, player_b_name, season_a=None, season_b=None):
        """
        Simulate a bidirectional trade with optional cross-season player metrics.
        
        Args:
            team_a: Team trading player A (uses current season roster)
            player_a_name: Name of player A
            team_b: Team trading player B (uses current season roster)
            player_b_name: Name of player B
            season_a: Season to use for player A's metrics (default: current season)
            season_b: Season to use for player B's metrics (default: current season)
        """
        # Default to current season if not specified
        if season_a is None:
            season_a = self.current_season
        if season_b is None:
            season_b = self.current_season
        
        # Get player data for the specified seasons
        player_data_a = self.player_data_all[self.player_data_all['season'] == season_a]
        player_data_b = self.player_data_all[self.player_data_all['season'] == season_b]
        
        # Find player A in their specified season
        player_a_matches = player_data_a[
            (player_data_a['name'] == player_a_name) &
            (player_data_a['team'] == team_a)
        ]
        
        if len(player_a_matches) == 0:
            # Try fuzzy match
            player_a_matches = player_data_a[
                player_data_a['name'].str.contains(player_a_name, case=False, na=False) &
                (player_data_a['team'] == team_a)
            ]
        
        if len(player_a_matches) == 0:
            return {'success': False, 'error': f'Player "{player_a_name}" not found on {team_a} in {season_a}'}
        
        player_a = player_a_matches.iloc[0]
        
        # Find player B in their specified season
        player_b_matches = player_data_b[
            (player_data_b['name'] == player_b_name) &
            (player_data_b['team'] == team_b)
        ]
        
        if len(player_b_matches) == 0:
            # Try fuzzy match
            player_b_matches = player_data_b[
                player_data_b['name'].str.contains(player_b_name, case=False, na=False) &
                (player_data_b['team'] == team_b)
            ]
        
        if len(player_b_matches) == 0:
            return {'success': False, 'error': f'Player "{player_b_name}" not found on {team_b} in {season_b}'}
        
        player_b = player_b_matches.iloc[0]
        
        # Get actual team metrics from team_season_metrics as baseline (pre-trade)
        # Convert abbreviations to full team names for matching
        team_a_full = self._get_full_team_name(team_a)
        team_b_full = self._get_full_team_name(team_b)
        
        team_a_data = self.team_data[
            (self.team_data['season'] == self.current_season) & 
            (self.team_data['team_full'] == team_a_full)
        ]
        team_b_data = self.team_data[
            (self.team_data['season'] == self.current_season) & 
            (self.team_data['team_full'] == team_b_full)
        ]
        
        if len(team_a_data) == 0 or len(team_b_data) == 0:
            missing = []
            if len(team_a_data) == 0:
                missing.append(f"{team_a} ({team_a_full})")
            if len(team_b_data) == 0:
                missing.append(f"{team_b} ({team_b_full})")
            return {'success': False, 'error': f'Team data not found for {self.current_season}: {", ".join(missing)}'}
        
        team_a_metrics_before = {m: team_a_data.iloc[0][m] for m in self.metrics_list}
        team_b_metrics_before = {m: team_b_data.iloc[0][m] for m in self.metrics_list}
        
        # Use standings model's precomputed ranks for consistency with Team Analysis tab
        team_a_rank_before = self.get_team_predicted_rank(team_a)
        team_b_rank_before = self.get_team_predicted_rank(team_b)
        
        # Calculate trade impact using delta method
        # Team A: loses player_a, gains player_b
        team_a_metrics_after = self.calculate_trade_impact(team_a, player_a, player_b)
        # Team B: loses player_b, gains player_a
        team_b_metrics_after = self.calculate_trade_impact(team_b, player_b, player_a)
        
        team_a_rank_after = self.predict_team_rank(team_a_metrics_after)
        team_b_rank_after = self.predict_team_rank(team_b_metrics_after)
        
        # Calculate percentiles for before/after metrics (relative to current season)
        team_a_pct_before = self._calculate_metric_percentiles(team_a_metrics_before)
        team_a_pct_after = self._calculate_metric_percentiles(team_a_metrics_after)
        team_b_pct_before = self._calculate_metric_percentiles(team_b_metrics_before)
        team_b_pct_after = self._calculate_metric_percentiles(team_b_metrics_after)
        
        return {
            'success': True,
            'player_a': {
                'name': player_a['name'],
                'position': player_a['position'],
                'icetime': player_a['icetime'],
                'games_played': player_a['games_played'],
                'season': season_a
            },
            'player_b': {
                'name': player_b['name'],
                'position': player_b['position'],
                'icetime': player_b['icetime'],
                'games_played': player_b['games_played'],
                'season': season_b
            },
            'team_a': {
                'name': team_a,
                'rank_before': team_a_rank_before,
                'rank_after': team_a_rank_after,
                'rank_change': team_a_rank_after - team_a_rank_before,
                'loses': player_a['name'],
                'gains': player_b['name'],
                'metrics_before': team_a_metrics_before,
                'metrics_after': team_a_metrics_after,
                'percentiles_before': team_a_pct_before,
                'percentiles_after': team_a_pct_after
            },
            'team_b': {
                'name': team_b,
                'rank_before': team_b_rank_before,
                'rank_after': team_b_rank_after,
                'rank_change': team_b_rank_after - team_b_rank_before,
                'loses': player_b['name'],
                'gains': player_a['name'],
                'metrics_before': team_b_metrics_before,
                'metrics_after': team_b_metrics_after,
                'percentiles_before': team_b_pct_before,
                'percentiles_after': team_b_pct_after
            },
            'current_season': self.current_season
        }
    
    def identify_team_weaknesses(self, team):
        """Identify team weaknesses compared to league average"""
        roster = self.get_team_roster(team)
        
        goalie_row = self.goalie_data[self.goalie_data['team'] == team]
        goalie_metrics = {
            'save_percentage': goalie_row.iloc[0]['save_percentage'] if len(goalie_row) > 0 else 0.910,
            'goals_saved_above_expected': goalie_row.iloc[0]['goals_saved_above_expected'] if len(goalie_row) > 0 else 0.0
        }
        
        metrics = self.calculate_team_metrics_from_roster(roster, goalie_metrics)
        
        if metrics is None:
            return {}
        
        league_df = self.team_data[self.team_data['season'] == 2024]
        
        weaknesses = {}
        for metric in self.metrics_list:
            if metric in metrics and metric in league_df.columns:
                current_value = metrics[metric]
                league_values = league_df[metric].dropna()
                
                if len(league_values) > 0:
                    percentile = (league_values < current_value).mean() * 100
                    league_avg = league_values.mean()
                    
                    if percentile < 40:
                        weaknesses[metric] = {
                            'current_value': current_value,
                            'league_average': league_avg,
                            'percentile': percentile,
                            'gap': league_avg - current_value
                        }
        
        return weaknesses
