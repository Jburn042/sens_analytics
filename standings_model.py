"""
NHL Standings Model

Predicts team standings based on underlying performance metrics.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, train_test_split
import warnings
warnings.filterwarnings('ignore')
from load_data import load_team_season_metrics


class StandingsModel:
    """NHL Standings Prediction Model"""
    
    def __init__(self):
        # Core metrics used for model predictions (5v5 only)
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
        
        # Display-only metrics (not used in model, but shown in radar)
        self.display_metrics = [
            'pp_pct',
            'pk_pct'
        ]
        
        # All metrics for display purposes
        self.all_display_metrics = self.metrics_list + self.display_metrics
        
        self.metric_descriptions = {
            'net_flurry_xgoals': 'Expected goals differential during high-intensity sequences',
            'net_score_adjusted_shots': 'Shot attempts differential adjusted for game situation',
            'corsipercentage': 'Percentage of all shot attempts taken by the team at 5v5',
            'save_percentage': 'Percentage of shots on goal that were saved',
            'net_high_danger_shots': 'High-danger shot attempts differential (close to net)',
            'goals_saved_above_expected': 'Goals prevented beyond what expected goals model predicted',
            'net_high_danger_xgoals': 'Expected goals differential from high-danger chances',
            'shooting_percentage': 'Percentage of shots on goal that resulted in goals',
            'pp_pct': 'Power play percentage - goals scored per power play opportunity',
            'pk_pct': 'Penalty kill percentage - percentage of penalties successfully killed'
        }
        
        # Load data
        self.df_read = load_team_season_metrics()
        
        # Filter to complete seasons for training (exclude current incomplete season)
        current_season = 2025
        self.df_read_training = self.df_read[self.df_read['season'] < current_season].copy()
        
        # Train model
        self.model, self.feature_importances = self._train_model()
        
        # Calculate predictions
        self.df_results = self._calculate_predictions()
    
    def _train_model(self):
        """Train the Random Forest model"""
        X = self.df_read_training[self.metrics_list]
        y = self.df_read_training['team_rank']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        param_grid = {
            'n_estimators': [100, 200],
            'max_depth': [None, 10, 20],
            'min_samples_split': [2, 5]
        }
        
        rf = RandomForestRegressor(random_state=42)
        grid_search = GridSearchCV(rf, param_grid, cv=5, scoring='neg_mean_squared_error')
        grid_search.fit(X_train, y_train)
        
        feature_importances = dict(zip(self.metrics_list, grid_search.best_estimator_.feature_importances_))
        
        return grid_search.best_estimator_, feature_importances
    
    def _calculate_predictions(self):
        """Calculate predictions and variance analysis"""
        df = self.df_read.copy()
        
        df['predicted_rank'] = self.model.predict(df[self.metrics_list])
        
        # Include both model metrics and display-only metrics
        cols_to_include = ['season', 'team_full', 'team_rank', 'predicted_rank'] + self.metrics_list
        for m in self.display_metrics:
            if m in df.columns:
                cols_to_include.append(m)
        
        df_results = df[cols_to_include].copy()
        
        df_results = df_results.sort_values(by=['season', 'predicted_rank'])
        df_results['predicted_rank_placement'] = df_results.groupby('season').cumcount() + 1
        df_results['ranking_variance'] = df_results['team_rank'] - df_results['predicted_rank_placement']
        
        # Add analytical columns for model metrics
        for metric in self.metrics_list:
            df_results[f'{metric}_percentile'] = df_results.groupby('season')[metric].rank(pct=True) * 100
            df_results[f'{metric}_zscore'] = df_results.groupby('season')[metric].transform(
                lambda x: (x - x.mean()) / x.std()
            )
            df_results[f'{metric}_variance_contribution'] = (
                abs(df_results[f'{metric}_zscore']) * 
                self.feature_importances[metric] * 
                np.sign(df_results['ranking_variance'])
            )
        
        # Add percentiles for display-only metrics (no variance contribution)
        for metric in self.display_metrics:
            if metric in df_results.columns:
                df_results[f'{metric}_percentile'] = df_results.groupby('season')[metric].rank(pct=True) * 100
        
        return df_results
    
    def get_correlations(self):
        """Get metric correlations with team rank"""
        from scipy import stats
        correlations = {}
        for metric in self.metrics_list:
            corr, pval = stats.pearsonr(self.df_read_training['team_rank'], self.df_read_training[metric])
            correlations[metric] = {'correlation': corr, 'pvalue': pval}
        return correlations
    
    def analyze_team_prediction(self, team_name, season):
        """Detailed analysis of a specific team's prediction variance"""
        team_data = self.df_results[
            (self.df_results['team_full'] == team_name) & 
            (self.df_results['season'] == season)
        ]
        
        if len(team_data) == 0:
            return None
        
        team_row = team_data.iloc[0]
        
        season_data = self.df_results[self.df_results['season'] == season]
        league_avgs = {metric: season_data[metric].mean() for metric in self.metrics_list}
        
        variance_contributions = {
            metric: abs(team_row[f'{metric}_variance_contribution'])
            for metric in self.metrics_list
        }
        biggest_driver = max(variance_contributions, key=variance_contributions.get)
        
        # Calculate biggest strength and weakness based on percentiles
        percentiles = {
            metric: team_row[f'{metric}_percentile']
            for metric in self.metrics_list
        }
        biggest_strength = max(percentiles, key=percentiles.get)
        biggest_weakness = min(percentiles, key=percentiles.get)
        
        analysis = {
            'team_name': team_name,
            'season': season,
            'actual_rank': int(team_row['team_rank']),
            'predicted_rank': int(team_row['predicted_rank_placement']),
            'variance': int(team_row['ranking_variance']),
            'biggest_driver': biggest_driver,
            'biggest_strength': biggest_strength,
            'biggest_strength_percentile': float(percentiles[biggest_strength]),
            'biggest_weakness': biggest_weakness,
            'biggest_weakness_percentile': float(percentiles[biggest_weakness]),
            'metrics': {}
        }
        
        for metric in self.metrics_list:
            analysis['metrics'][metric] = {
                'value': float(team_row[metric]),
                'league_avg': float(league_avgs[metric]),
                'percentile': float(team_row[f'{metric}_percentile']),
                'zscore': float(team_row[f'{metric}_zscore']),
                'model_weight': float(self.feature_importances[metric] * 100),
                'description': self.metric_descriptions[metric],
                'variance_contribution': float(team_row[f'{metric}_variance_contribution'])
            }
        
        # Add display-only metrics (PP/PK) - not used in model predictions
        for metric in self.display_metrics:
            if metric in team_row.index and f'{metric}_percentile' in team_row.index:
                display_league_avg = season_data[metric].mean() if metric in season_data.columns else 0
                analysis['metrics'][metric] = {
                    'value': float(team_row[metric]),
                    'league_avg': float(display_league_avg),
                    'percentile': float(team_row[f'{metric}_percentile']),
                    'zscore': 0,  # Not calculated for display metrics
                    'model_weight': 0,  # Not used in model
                    'description': self.metric_descriptions.get(metric, ''),
                    'variance_contribution': 0  # Not used in model
                }
        
        return analysis
    
    def get_top_variance_cases(self, season, top_n=5):
        """Get teams with highest prediction errors for a season"""
        season_data = self.df_results[self.df_results['season'] == season].copy()
        season_data['abs_variance'] = season_data['ranking_variance'].abs()
        top_cases = season_data.nlargest(top_n, 'abs_variance')
        
        results = []
        for _, row in top_cases.iterrows():
            variance_contributions = {
                metric: abs(row[f'{metric}_variance_contribution'])
                for metric in self.metrics_list
            }
            biggest_driver = max(variance_contributions, key=variance_contributions.get)
            
            results.append({
                'team': row['team_full'],
                'actual_rank': int(row['team_rank']),
                'predicted_rank': int(row['predicted_rank_placement']),
                'variance': int(row['ranking_variance']),
                'driver': biggest_driver,
                'driver_value': float(row[biggest_driver]),
                'driver_percentile': float(row[f'{biggest_driver}_percentile']),
                'driver_zscore': float(row[f'{biggest_driver}_zscore'])
            })
        
        return results
    
    def get_all_teams_for_season(self, season):
        """Get all teams for a specific season"""
        season_data = self.df_results[self.df_results['season'] == season]
        return sorted(season_data['team_full'].unique())
    
    def get_available_seasons(self):
        """Get list of available seasons"""
        return sorted(self.df_results['season'].unique())
