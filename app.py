"""
Sens Friendly Analytics Hub - Streamlit App
Standings Model + Roster Simulation

Self-contained app with authentication for deployment.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from standings_model import StandingsModel
from roster_simulation import RosterSimulator
from load_data import get_data_last_updated, check_data_availability, load_player_data, load_player_data_all
from auth import check_password

# Page configuration
st.set_page_config(
    page_title="Sens Friendly Analytics Hub",
    page_icon="sens_logo.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - compatible with dark mode
st.markdown("""
    <style>
    .metric-card {
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    [data-testid="column"]:first-child {
        display: flex;
        align-items: center;
        padding-top: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# Check authentication first
if not check_password():
    st.stop()

@st.cache_resource
def load_standings_model():
    """Load the standings model (cached)"""
    return StandingsModel()

@st.cache_resource
def load_roster_simulator(_standings_model, season=2025):
    """Load the roster simulator (cached), sharing the standings model"""
    return RosterSimulator(season=season, standings_model=_standings_model)

def format_percentile(pct):
    """Format percentile with color coding"""
    if pct >= 75:
        return f"{pct:.0f}th percentile (Excellent)"
    elif pct >= 60:
        return f"{pct:.0f}th percentile (Above Average)"
    elif pct >= 40:
        return f"{pct:.0f}th percentile (Average)"
    elif pct >= 25:
        return f"{pct:.0f}th percentile (Below Average)"
    else:
        return f"{pct:.0f}th percentile (Poor)"

def main():
    # Display logo and title
    col1, col2 = st.columns([1, 11], vertical_alignment="center")
    with col1:
        st.image("sens_logo.svg", width=60)
    with col2:
        st.markdown("# Sens Friendly Analytics Hub")
    
    # Sidebar
    st.sidebar.title("Sens Friendly Analytics")
    st.sidebar.markdown("---")
    
    # Data status
    st.sidebar.caption(f"Data updated: {get_data_last_updated()}")
    
    # Run the standings model (includes all tools now)
    run_standings_model()

# ==================== STANDINGS MODEL ====================

def run_standings_model():
    """Run the standings prediction model"""
    st.markdown("### Team Performance Prediction & Analysis")
    
    # Check data availability
    availability = check_data_availability()
    if not availability['team_season_metrics']:
        st.error("Data files not found. Please run the data pipeline first.")
        st.code("cd pipeline && python fetch_data.py && python process_data.py")
        return
    
    with st.spinner("Loading models..."):
        model = load_standings_model()
        simulator = load_roster_simulator(model)
    
    tab1, tab2, tab3 = st.tabs(["Team Analysis", "Player Comparison", "Trade Simulator"])
    
    with tab1:
        show_standings_team_analysis(model)
    with tab2:
        show_player_comparison()
    with tab3:
        show_trade_simulator(simulator)

def show_standings_team_analysis(model):
    """Team analysis page"""
    st.header("Team Prediction Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        season = st.selectbox(
            "Select Season:",
            model.get_available_seasons(),
            index=len(model.get_available_seasons()) - 1,
            key='team_analysis_season'
        )
    
    with col2:
        teams = model.get_all_teams_for_season(season)
        
        # Get default index - Ottawa if available, else first team
        default_idx = teams.index('Ottawa Senators') if 'Ottawa Senators' in teams else 0
        
        # Simple selectbox - let Streamlit manage state via key
        team = st.selectbox("Select Team:", teams, index=default_idx, key='main_team_select')
    
    analysis = model.analyze_team_prediction(team, season)
    
    if analysis is None:
        st.error("No data available")
        return
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Actual Rank", analysis['actual_rank'])
    with col2:
        st.metric("Predicted Rank", analysis['predicted_rank'])
    with col3:
        variance = analysis['variance']
        direction = "BETTER" if variance < 0 else "WORSE"
        st.metric("Performance Gap", f"{abs(variance)} spots {direction}")
    
    # Strength and Weakness row
    col1, col2 = st.columns(2)
    
    with col1:
        strength_name = analysis['biggest_strength'].replace('_', ' ').title()
        strength_pct = analysis['biggest_strength_percentile']
        st.metric("Biggest Strength", f"{strength_name}", delta=f"{strength_pct:.0f}th percentile")
    
    with col2:
        weakness_name = analysis['biggest_weakness'].replace('_', ' ').title()
        weakness_pct = analysis['biggest_weakness_percentile']
        st.metric("Biggest Weakness", f"{weakness_name}", delta=f"{weakness_pct:.0f}th percentile", delta_color="inverse")
    
    # Plain-English explanation of performance
    METRIC_EXPLANATIONS = {
        'net_flurry_xgoals': 'scoring chances during high-pressure sequences',
        'net_score_adjusted_shots': 'shot volume and territorial control',
        'corsi_pct': 'puck possession',
        'save_pct': 'goaltending',
        'net_hd_shots': 'high-danger scoring chances',
        'gsax': 'goaltending (goals saved above expected)',
        'net_hd_xgoals': 'quality scoring opportunities',
        'shooting_pct': 'finishing ability (converting shots to goals)'
    }
    
    weakness_explanation = METRIC_EXPLANATIONS.get(analysis['biggest_weakness'], weakness_name.lower())
    strength_explanation = METRIC_EXPLANATIONS.get(analysis['biggest_strength'], strength_name.lower())
    
    if variance > 3:
        # Underperforming - weakness is likely the culprit
        if weakness_pct < 20:
            explanation = f"Poor {weakness_explanation} ({weakness_pct:.0f}th percentile) is dragging down {team}. Despite solid underlying metrics, they're losing games they should be winning."
        else:
            explanation = f"{team} is underperforming their underlying numbers. Bad luck, close losses, or inconsistency may be factors."
        st.warning(f"**Why the gap?** {explanation}")
    elif variance < -3:
        # Overperforming - strength or luck is helping
        if strength_pct > 80:
            explanation = f"Elite {strength_explanation} ({strength_pct:.0f}th percentile) is carrying {team}. They're winning more than expected based on overall play."
        else:
            explanation = f"{team} is outperforming their metrics. Strong goaltending, clutch scoring, or favorable bounces may be helping."
        st.success(f"**Why the gap?** {explanation}")
    else:
        st.info(f"**{team}** is performing roughly as expected based on their underlying metrics.")
    
    st.markdown("---")
    st.subheader("Team Performance Radar")
    
    # Clean display names for metrics
    METRIC_DISPLAY_NAMES = {
        'net_flurry_xgoals': 'Flurry xGoals',
        'net_score_adjusted_shots': 'Shot Differential',
        'corsipercentage': 'Corsi %',
        'save_percentage': 'Save %',
        'net_high_danger_shots': 'HD Shots',
        'goals_saved_above_expected': 'GSAx',
        'net_high_danger_xgoals': 'HD xGoals',
        'shooting_percentage': 'Shooting %',
        'pp_pct': 'Power Play %',
        'pk_pct': 'Penalty Kill %'
    }
    
    # Metric descriptions for the reference section
    METRIC_DEFINITIONS = {
        'Flurry xGoals': 'Expected goals differential during high-intensity scoring sequences. Higher = better offensive bursts.',
        'Shot Differential': 'Shot attempts for minus against, adjusted for game score. Higher = more offensive pressure.',
        'Corsi %': 'Percentage of all 5v5 shot attempts taken by your team. 50% is average; >55% is elite.',
        'Save %': 'Percentage of shots on goal stopped by goalies. League average is ~.905.',
        'HD Shots': 'High-danger shot attempts (close to net) differential. Higher = more quality chances.',
        'GSAx': 'Goals Saved Above Expected - how many goals your goalies prevented vs expected. Positive = good goaltending.',
        'HD xGoals': 'Expected goals from high-danger chances differential. Higher = better quality offense.',
        'Shooting %': 'Percentage of shots that become goals. Varies by luck and finishing skill.',
        'Power Play %': 'Percentage of power plays that result in a goal. League average is ~20%.',
        'Penalty Kill %': 'Percentage of penalties successfully killed without allowing a goal. League average is ~80%.'
    }
    
    teams_for_comparison = model.get_all_teams_for_season(season)
    
    # Track the previous main team to detect changes
    if 'radar_prev_main_team' not in st.session_state:
        st.session_state.radar_prev_main_team = team
    if 'radar_additional_teams' not in st.session_state:
        st.session_state.radar_additional_teams = []
    
    # Detect if main team changed
    main_team_changed = st.session_state.radar_prev_main_team != team
    st.session_state.radar_prev_main_team = team
    
    # Keep additional teams that exist in the current season (excluding the main team)
    valid_additional = [t for t in st.session_state.radar_additional_teams 
                        if t in teams_for_comparison and t != team]
    
    # Build the new selection: main team first, then any additional teams
    new_selection = [team] + valid_additional if team in teams_for_comparison else valid_additional
    if not new_selection:
        new_selection = [teams_for_comparison[0]]
    
    # If main team changed, update the widget's session state directly
    if main_team_changed and 'radar_multiselect' in st.session_state:
        st.session_state.radar_multiselect = new_selection
    
    selected_teams = st.multiselect(
        "Select teams to compare:",
        teams_for_comparison,
        default=new_selection,
        max_selections=5,
        key='radar_multiselect'
    )
    
    # Store additional teams (everything except the main selected team)
    st.session_state.radar_additional_teams = [t for t in selected_teams if t != team]
    
    if selected_teams:
        # Define a pleasing color palette
        colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A', '#9B5DE5']
        
        fig_spider = go.Figure()
        
        for idx, selected_team in enumerate(selected_teams):
            team_analysis = model.analyze_team_prediction(selected_team, season)
            if team_analysis:
                display_names = []
                percentiles = []
                
                for metric, data in team_analysis['metrics'].items():
                    display_names.append(METRIC_DISPLAY_NAMES.get(metric, metric.replace('_', ' ').title()))
                    percentiles.append(data['percentile'])
                
                # Close the polygon
                display_names.append(display_names[0])
                percentiles.append(percentiles[0])
                
                team_color = colors[idx % len(colors)]
                
                fig_spider.add_trace(go.Scatterpolar(
                    r=percentiles,
                    theta=display_names,
                    fill='toself',
                    name=selected_team,
                    line=dict(width=3, color=team_color),
                    fillcolor=team_color,
                    opacity=0.4,
                    hovertemplate='<b>%{theta}</b><br>%{r:.0f}th percentile<extra>' + selected_team + '</extra>'
                ))
        
        fig_spider.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickvals=[25, 50, 75, 100],
                    ticktext=['25%', '50%', '75%', '100%'],
                    tickfont=dict(size=12, color='gray'),
                    gridcolor='rgba(128,128,128,0.3)',
                    linecolor='rgba(128,128,128,0.5)'
                ),
                angularaxis=dict(
                    tickfont=dict(size=14, color='white'),
                    linecolor='rgba(128,128,128,0.5)',
                    gridcolor='rgba(128,128,128,0.3)'
                ),
                bgcolor='rgba(0,0,0,0)'
            ),
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.15,
                xanchor='center',
                x=0.5,
                font=dict(size=14)
            ),
            height=700,
            margin=dict(t=40, b=100, l=100, r=100),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_spider, use_container_width=True)
        
        # Percentile guide
        st.markdown("""
        <div style="text-align: center; padding: 10px; background: rgba(128,128,128,0.1); border-radius: 8px; margin-bottom: 20px;">
            <span style="color: #E63946;">●</span> <b>0-25%</b> Poor &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #E9C46A;">●</span> <b>25-50%</b> Below Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #457B9D;">●</span> <b>50-75%</b> Above Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #2A9D8F;">●</span> <b>75-100%</b> Excellent
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("*Power Play and Penalty Kill are shown for context but are not used in the prediction model (which focuses on 5v5 play)*")
        
        # Metric definitions expander
        with st.expander("📊 What do these metrics mean?", expanded=False):
            col1, col2 = st.columns(2)
            metrics_items = list(METRIC_DEFINITIONS.items())
            half = len(metrics_items) // 2 + len(metrics_items) % 2
            
            with col1:
                for name, desc in metrics_items[:half]:
                    st.markdown(f"**{name}**")
                    st.caption(desc)
                    st.markdown("")
            
            with col2:
                for name, desc in metrics_items[half:]:
                    st.markdown(f"**{name}**")
                    st.caption(desc)
                    st.markdown("")
    
    # ==================== TOP VARIANCE SECTION ====================
    st.markdown("---")
    with st.expander("📉 Top Prediction Variance Cases", expanded=False):
        top_n = st.slider("Number of teams to show:", 3, 15, 5, key='variance_slider')
        
        variance_cases = model.get_top_variance_cases(season, top_n)
        
        for i, case in enumerate(variance_cases, 1):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.subheader(f"{i}. {case['team']}")
                with col2:
                    st.metric("Actual", case['actual_rank'])
                with col3:
                    st.metric("Predicted", case['predicted_rank'])
                with col4:
                    variance_val = case['variance']
                    direction = "better" if variance_val < 0 else "worse"
                    st.metric("Delta", f"{abs(variance_val)} {direction}")
                
                st.markdown(f"**Driver:** {case['driver'].replace('_', ' ').title()} - {format_percentile(case['driver_percentile'])}")
                st.markdown("---")
    
    # ==================== MODEL OVERVIEW SECTION ====================
    with st.expander("🔬 Model Overview", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Teams", len(model.df_results))
        with col2:
            st.metric("Seasons", f"{min(model.get_available_seasons())}-{max(model.get_available_seasons())}")
        with col3:
            avg_variance = model.df_results['ranking_variance'].abs().mean()
            st.metric("Avg Error", f"{avg_variance:.1f} spots")
        with col4:
            st.metric("Core Metrics", len(model.metrics_list))
        
        st.markdown("---")
        
        st.markdown("""
        ### Random Forest Prediction Model
        
        - **Algorithm:** Random Forest Regressor with Grid Search
        - **Training:** 80% train / 20% test split
        - **Cross-Validation:** 5-fold CV
        - **Features:** 8 hockey performance metrics
        - **Target:** Team standings position (1-32)
        - **Data:** 5v5 play only
        
        ### Philosophy
        
        Process over results. Predicts where teams *should* finish based on underlying metrics.
        """)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Feature Importance")
            importance_df = pd.DataFrame([
                {'Metric': k, 'Importance': v * 100} 
                for k, v in model.feature_importances.items()
            ]).sort_values('Importance', ascending=False)
            
            fig = px.bar(importance_df, x='Importance', y='Metric', orientation='h',
                         color='Importance', color_continuous_scale='Blues')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Correlations with Rank")
            correlations = model.get_correlations()
            corr_df = pd.DataFrame([
                {'Metric': k, 'Correlation': v['correlation']}
                for k, v in correlations.items()
            ]).sort_values('Correlation')
            
            fig = px.bar(corr_df, x='Correlation', y='Metric', orientation='h',
                         color='Correlation', color_continuous_scale='RdBu',
                         color_continuous_midpoint=0)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

@st.fragment
def show_player_comparison():
    """Player comparison radar chart"""
    st.header("Player Comparison")
    st.caption("Compare player performance metrics across seasons and teams")
    
    # Load both data sources
    try:
        player_df_all = load_player_data_all()  # For total stats (GP, Points, Goals)
        player_df_5on5 = load_player_data()     # For analytical metrics (5on5)
    except FileNotFoundError as e:
        st.error(f"Player data not found. Run the data pipeline first: {e}")
        return
    
    # Filter to reasonable sample (min 20 games) - use all-situations for selection
    player_df_all = player_df_all[player_df_all['games_played'] >= 20].copy()
    player_df_5on5 = player_df_5on5[player_df_5on5['games_played'] >= 20].copy()
    
    # Player metrics to compare (per 60 minutes where applicable) - calculated from 5on5 data
    PLAYER_METRICS = {
        'gameScore': {'name': 'Game Score', 'desc': 'Overall game impact rating (5v5)', 'per60': False},
        'I_F_goals_per60': {'name': 'Goals/60', 'desc': '5v5 goals per 60 minutes', 'per60': True, 'raw': 'I_F_goals'},
        'I_F_points_per60': {'name': 'Points/60', 'desc': '5v5 points per 60 minutes', 'per60': True, 'raw': 'I_F_points'},
        'I_F_xGoals_per60': {'name': 'xGoals/60', 'desc': 'Expected goals per 60 minutes', 'per60': True, 'raw': 'I_F_xGoals'},
        'onIce_xGoalsPercentage': {'name': 'On-Ice xG%', 'desc': 'Expected goals for % when on ice', 'per60': False},
        'onIce_corsiPercentage': {'name': 'On-Ice Corsi%', 'desc': 'Shot attempt % when on ice', 'per60': False},
        'I_F_highDangerShots_per60': {'name': 'HD Shots/60', 'desc': 'High-danger shots per 60 min', 'per60': True, 'raw': 'I_F_highDangerShots'},
        'I_F_hits_per60': {'name': 'Hits/60', 'desc': 'Hits per 60 minutes', 'per60': True, 'raw': 'I_F_hits'},
    }
    
    # Calculate per-60 metrics on 5on5 data
    for metric_key, metric_info in PLAYER_METRICS.items():
        if metric_info.get('per60') and 'raw' in metric_info:
            raw_col = metric_info['raw']
            if raw_col in player_df_5on5.columns:
                player_df_5on5[metric_key] = (player_df_5on5[raw_col] / player_df_5on5['icetime']) * 3600
    
    # Get available seasons from all-situations data (for selection)
    seasons = sorted(player_df_all['season'].unique(), reverse=True)
    
    st.markdown("---")
    st.subheader("Select Players to Compare")
    
    # Helper to get player index (preserves selection when changing season/team)
    def get_player_index(players_list, stored_key):
        if stored_key in st.session_state:
            stored_name = st.session_state[stored_key]
            if stored_name in players_list:
                return players_list.index(stored_name)
        return 0
    
    # Player 1 selection
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Player 1**")
        season1 = st.selectbox("Season", seasons, key='player1_season')
        
        # Get teams for this season
        teams1 = sorted(player_df_all[player_df_all['season'] == season1]['team'].unique())
        team1_idx = get_player_index(teams1, 'player1_team')
        team1 = st.selectbox("Team", teams1, index=team1_idx, key='player1_team')
        
        # Get players for this team/season - preserve player selection across season changes
        all_players_with_name = player_df_all[player_df_all['name'].isin(
            player_df_all[(player_df_all['season'] == season1) & (player_df_all['team'] == team1)]['name']
        )]
        players1 = sorted(player_df_all[(player_df_all['season'] == season1) & (player_df_all['team'] == team1)]['name'].unique())
        player1_idx = get_player_index(players1, 'player1_name')
        player1_name = st.selectbox("Player", players1, index=player1_idx, key='player1_name')
    
    with col2:
        st.markdown("**Player 2**")
        season2 = st.selectbox("Season", seasons, key='player2_season')
        
        teams2 = sorted(player_df_all[player_df_all['season'] == season2]['team'].unique())
        team2_idx = get_player_index(teams2, 'player2_team')
        team2 = st.selectbox("Team", teams2, index=team2_idx, key='player2_team')
        
        players2 = sorted(player_df_all[(player_df_all['season'] == season2) & (player_df_all['team'] == team2)]['name'].unique())
        player2_idx = get_player_index(players2, 'player2_name')
        player2_name = st.selectbox("Player", players2, index=player2_idx, key='player2_name') if players2 else None
    
    if player1_name and player2_name:
        # Get player total stats from all-situations data
        p1_all = player_df_all[(player_df_all['season'] == season1) & (player_df_all['team'] == team1) & (player_df_all['name'] == player1_name)]
        p2_all = player_df_all[(player_df_all['season'] == season2) & (player_df_all['team'] == team2) & (player_df_all['name'] == player2_name)]
        
        # Get player 5on5 data for radar chart
        p1_5on5 = player_df_5on5[(player_df_5on5['season'] == season1) & (player_df_5on5['team'] == team1) & (player_df_5on5['name'] == player1_name)]
        p2_5on5 = player_df_5on5[(player_df_5on5['season'] == season2) & (player_df_5on5['team'] == team2) & (player_df_5on5['name'] == player2_name)]
        
        if p1_all.empty or p2_all.empty:
            st.warning("Could not find complete data for selected players.")
            return
        
        p1_all_row = p1_all.iloc[0]
        p2_all_row = p2_all.iloc[0]
        
        # Calculate percentiles within each player's season (using 5on5 data)
        def get_player_percentiles(player_row, season, metrics):
            season_df = player_df_5on5[player_df_5on5['season'] == season]
            percentiles = {}
            for metric_key in metrics:
                if metric_key in season_df.columns and metric_key in player_row.index:
                    val = player_row[metric_key]
                    pct = (season_df[metric_key] < val).mean() * 100
                    percentiles[metric_key] = pct
            return percentiles
        
        metric_keys = [k for k in PLAYER_METRICS.keys() if k in player_df_5on5.columns]
        
        # Get percentiles (only if 5on5 data exists)
        p1_percentiles = {}
        p2_percentiles = {}
        if not p1_5on5.empty:
            p1_percentiles = get_player_percentiles(p1_5on5.iloc[0], season1, metric_keys)
        if not p2_5on5.empty:
            p2_percentiles = get_player_percentiles(p2_5on5.iloc[0], season2, metric_keys)
        
        # Display key stats (from ALL-SITUATIONS data = total stats) - compact card layout
        st.markdown("---")
        
        # Compact player comparison cards
        p1_gp = int(p1_all_row['games_played'])
        p1_pts = int(p1_all_row.get('I_F_points', 0))
        p1_g = int(p1_all_row.get('I_F_goals', 0))
        p1_a = p1_pts - p1_g  # Assists = Points - Goals
        p1_hits = int(p1_all_row.get('I_F_hits', 0))
        p1_blk = int(p1_all_row.get('shotsBlockedByPlayer', 0))
        
        p2_gp = int(p2_all_row['games_played'])
        p2_pts = int(p2_all_row.get('I_F_points', 0))
        p2_g = int(p2_all_row.get('I_F_goals', 0))
        p2_a = p2_pts - p2_g
        p2_hits = int(p2_all_row.get('I_F_hits', 0))
        p2_blk = int(p2_all_row.get('shotsBlockedByPlayer', 0))
        
        st.markdown(f"""
        <div style="display: flex; gap: 20px; margin-bottom: 20px;">
            <div style="flex: 1; padding: 15px; background: rgba(230, 57, 70, 0.15); border-radius: 10px; border-left: 4px solid #E63946;">
                <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 8px;">{player1_name}</div>
                <div style="color: gray; font-size: 0.85em; margin-bottom: 10px;">{team1} • {season1}</div>
                <div style="display: flex; flex-wrap: wrap; gap: 15px;">
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_gp}</span> <span style="color: gray;">GP</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_g}</span> <span style="color: gray;">G</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_a}</span> <span style="color: gray;">A</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_pts}</span> <span style="color: gray;">PTS</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_hits}</span> <span style="color: gray;">HIT</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_blk}</span> <span style="color: gray;">BLK</span></div>
                </div>
            </div>
            <div style="flex: 1; padding: 15px; background: rgba(69, 123, 157, 0.15); border-radius: 10px; border-left: 4px solid #457B9D;">
                <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 8px;">{player2_name}</div>
                <div style="color: gray; font-size: 0.85em; margin-bottom: 10px;">{team2} • {season2}</div>
                <div style="display: flex; flex-wrap: wrap; gap: 15px;">
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_gp}</span> <span style="color: gray;">GP</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_g}</span> <span style="color: gray;">G</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_a}</span> <span style="color: gray;">A</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_pts}</span> <span style="color: gray;">PTS</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_hits}</span> <span style="color: gray;">HIT</span></div>
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_blk}</span> <span style="color: gray;">BLK</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Build radar chart
        st.markdown("---")
        st.subheader("Performance Radar (League Percentiles)")
        st.caption("*5v5 (even-strength) metrics - more analytically meaningful than total stats*")
        
        display_names = [PLAYER_METRICS[k]['name'] for k in metric_keys]
        p1_values = [p1_percentiles.get(k, 50) for k in metric_keys]
        p2_values = [p2_percentiles.get(k, 50) for k in metric_keys]
        
        # Close the polygon
        display_names_closed = display_names + [display_names[0]]
        p1_closed = p1_values + [p1_values[0]]
        p2_closed = p2_values + [p2_values[0]]
        
        fig = go.Figure()
        
        # Player 1
        fig.add_trace(go.Scatterpolar(
            r=p1_closed,
            theta=display_names_closed,
            fill='toself',
            name=f"{player1_name} ({season1})",
            line=dict(width=3, color='#E63946'),
            fillcolor='#E63946',
            opacity=0.4,
            hovertemplate=f'<b>{player1_name}</b> ({team1}, {season1})<br><br>' + '<b>%{theta}</b>: %{r:.0f}th percentile<extra></extra>'
        ))
        
        # Player 2
        fig.add_trace(go.Scatterpolar(
            r=p2_closed,
            theta=display_names_closed,
            fill='toself',
            name=f"{player2_name} ({season2})",
            line=dict(width=3, color='#457B9D'),
            fillcolor='#457B9D',
            opacity=0.4,
            hovertemplate=f'<b>{player2_name}</b> ({team2}, {season2})<br><br>' + '<b>%{theta}</b>: %{r:.0f}th percentile<extra></extra>'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickvals=[25, 50, 75, 100],
                    ticktext=['25%', '50%', '75%', '100%'],
                    tickfont=dict(size=12, color='gray'),
                    gridcolor='rgba(128,128,128,0.3)',
                    linecolor='rgba(128,128,128,0.5)'
                ),
                angularaxis=dict(
                    tickfont=dict(size=14, color='white'),
                    linecolor='rgba(128,128,128,0.5)',
                    gridcolor='rgba(128,128,128,0.3)'
                ),
                bgcolor='rgba(0,0,0,0)'
            ),
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.15,
                xanchor='center',
                x=0.5,
                font=dict(size=14)
            ),
            height=700,
            margin=dict(t=40, b=100, l=100, r=100),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Percentile guide
        st.markdown("""
        <div style="text-align: center; padding: 10px; background: rgba(128,128,128,0.1); border-radius: 8px; margin-bottom: 20px;">
            <span style="color: #E63946;">●</span> <b>0-25%</b> Poor &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #E9C46A;">●</span> <b>25-50%</b> Below Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #457B9D;">●</span> <b>50-75%</b> Above Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #2A9D8F;">●</span> <b>75-100%</b> Excellent
        </div>
        """, unsafe_allow_html=True)
        
        # Metric definitions
        with st.expander("📊 What do these metrics mean?", expanded=False):
            col1, col2 = st.columns(2)
            items = [(PLAYER_METRICS[k]['name'], PLAYER_METRICS[k]['desc']) for k in metric_keys]
            half = len(items) // 2 + len(items) % 2
            
            with col1:
                for name, desc in items[:half]:
                    st.markdown(f"**{name}**")
                    st.caption(desc)
                    st.markdown("")
            
            with col2:
                for name, desc in items[half:]:
                    st.markdown(f"**{name}**")
                    st.caption(desc)
                    st.markdown("")


# ==================== TRADE SIMULATOR ====================

def show_trade_impact_radar(team_name, pct_before, pct_after, season):
    """Show radar chart comparing before/after trade metrics for a team"""
    import plotly.graph_objects as go
    
    # Use same metric display names as standings model
    metric_labels = {
        'net_flurry_xgoals': 'xGoals Diff',
        'net_score_adjusted_shots': 'Shot Diff',
        'corsipercentage': 'Possession',
        'save_percentage': 'Save %',
        'net_high_danger_shots': 'HD Shots',
        'goals_saved_above_expected': 'GSAx',
        'net_high_danger_xgoals': 'HD xGoals',
        'shooting_percentage': 'Shooting %'
    }
    
    # Get metrics in consistent order
    metrics = list(metric_labels.keys())
    labels = [metric_labels[m] for m in metrics]
    
    # Get percentile values (ensure we have values for all metrics)
    before_values = [pct_before.get(m, 50) for m in metrics]
    after_values = [pct_after.get(m, 50) for m in metrics]
    
    # Close the radar chart (connect last point to first)
    labels_closed = labels + [labels[0]]
    before_closed = before_values + [before_values[0]]
    after_closed = after_values + [after_values[0]]
    
    fig = go.Figure()
    
    # Before trace (current state)
    fig.add_trace(go.Scatterpolar(
        r=before_closed,
        theta=labels_closed,
        fill='toself',
        fillcolor='rgba(99, 110, 250, 0.25)',
        line=dict(color='rgba(99, 110, 250, 1)', width=3),
        name=f'Before Trade',
        hovertemplate='<b>%{theta}</b><br>Before: %{r:.0f}th pct<extra></extra>'
    ))
    
    # After trace (post-trade)
    fig.add_trace(go.Scatterpolar(
        r=after_closed,
        theta=labels_closed,
        fill='toself',
        fillcolor='rgba(0, 204, 150, 0.25)',
        line=dict(color='rgba(0, 204, 150, 1)', width=3),
        name=f'After Trade',
        hovertemplate='<b>%{theta}</b><br>After: %{r:.0f}th pct<extra></extra>'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticktext=['0', '25', '50', '75', '100'],
                tickvals=[0, 25, 50, 75, 100],
                tickfont=dict(size=12, color='#888'),
                gridcolor='rgba(128, 128, 128, 0.4)'
            ),
            angularaxis=dict(
                tickfont=dict(size=14, color='#fff', family='Arial Black'),
                gridcolor='rgba(128, 128, 128, 0.4)'
            ),
            bgcolor='rgba(30, 30, 30, 0.9)'
        ),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.12,
            xanchor='center',
            x=0.5,
            font=dict(size=13, color='#fff')
        ),
        title=dict(
            text=f'<b>{team_name}</b>',
            font=dict(size=18, color='#fff'),
            x=0.5
        ),
        height=480,
        margin=dict(l=80, r=80, t=60, b=60),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def generate_trade_narrative(result):
    """Generate a plain-English narrative explaining the trade impact"""
    
    metric_names = {
        'net_flurry_xgoals': 'expected goals differential',
        'net_score_adjusted_shots': 'shot differential', 
        'corsipercentage': 'possession',
        'save_percentage': 'save percentage',
        'net_high_danger_shots': 'high-danger shots',
        'goals_saved_above_expected': 'goaltending (GSAx)',
        'net_high_danger_xgoals': 'high-danger expected goals',
        'shooting_percentage': 'shooting percentage'
    }
    
    narratives = []
    
    for team_key in ['team_a', 'team_b']:
        team_data = result[team_key]
        team_name = team_data['name']
        pct_before = team_data['percentiles_before']
        pct_after = team_data['percentiles_after']
        rank_before = team_data['rank_before']
        rank_after = team_data['rank_after']
        rank_change = team_data['rank_change']
        gains = team_data['gains']
        loses = team_data['loses']
        rank_context = team_data.get('rank_context', {})
        
        # Calculate changes
        changes = {}
        for metric, name in metric_names.items():
            before = pct_before.get(metric, 50)
            after = pct_after.get(metric, 50)
            changes[metric] = {'before': before, 'after': after, 'diff': after - before, 'name': name}
        
        # Find biggest improvements and drops
        improvements = [(m, c) for m, c in changes.items() if c['diff'] > 5]
        drops = [(m, c) for m, c in changes.items() if c['diff'] < -5]
        unchanged_weak = [(m, c) for m, c in changes.items() if c['before'] < 25 and abs(c['diff']) < 3]
        
        improvements.sort(key=lambda x: x[1]['diff'], reverse=True)
        drops.sort(key=lambda x: x[1]['diff'])
        
        # Calculate net improvement score (sum of percentile changes)
        total_improvement = sum(c['diff'] for c in changes.values())
        significant_improvements = len([c for c in changes.values() if c['diff'] > 10])
        significant_drops = len([c for c in changes.values() if c['diff'] < -10])
        
        # Build narrative
        parts = []
        parts.append(f"**{team_name}** ({rank_before} → {rank_after})")
        
        # Determine overall impact - consider both rank change AND metric improvements
        if rank_change < -3:
            parts.append(f"Trading {loses} for {gains} is a **significant upgrade**.")
        elif rank_change < 0:
            parts.append(f"Trading {loses} for {gains} provides a **solid improvement**.")
        elif rank_change == 0:
            # No rank change - but did they actually improve?
            if total_improvement > 50 and significant_improvements >= 2:
                # Big improvements but no rank change - explain why
                team_ahead = rank_context.get('team_ahead')
                gap = rank_context.get('gap_to_ahead')
                if team_ahead and gap:
                    parts.append(f"Trading {loses} for {gains} **significantly improves** the team, but **{team_ahead}** remains {gap:.1f} pts ahead.")
                else:
                    parts.append(f"Trading {loses} for {gains} **improves multiple areas**, but not enough to move up.")
            elif total_improvement > 20:
                team_ahead = rank_context.get('team_ahead')
                if team_ahead:
                    parts.append(f"Trading {loses} for {gains} is a **modest upgrade**, but not enough to catch **{team_ahead}**.")
                else:
                    parts.append(f"Trading {loses} for {gains} provides **marginal improvement**.")
            elif total_improvement < -20:
                team_behind = rank_context.get('team_behind')
                if team_behind:
                    parts.append(f"Trading {loses} for {gains} **weakens** the team, but still ahead of **{team_behind}**.")
                else:
                    parts.append(f"Trading {loses} for {gains} is a **slight downgrade**.")
            else:
                parts.append(f"Trading {loses} for {gains} is essentially a **lateral move**.")
        elif rank_change <= 3:
            parts.append(f"Trading {loses} for {gains} results in a **notable decline**.")
        else:
            parts.append(f"Trading {loses} for {gains} causes a **major decline**.")
        
        # Show top improvements
        if improvements:
            top_improvement = improvements[0]
            parts.append(f"• Improves {top_improvement[1]['name']} ({top_improvement[1]['before']:.0f}→{top_improvement[1]['after']:.0f} percentile)")
            if len(improvements) > 1:
                second = improvements[1]
                parts.append(f"• Improves {second[1]['name']} ({second[1]['before']:.0f}→{second[1]['after']:.0f} percentile)")
        
        # Show top drops
        if drops:
            top_drop = drops[0]
            parts.append(f"• Hurts {top_drop[1]['name']} ({top_drop[1]['before']:.0f}→{top_drop[1]['after']:.0f} percentile)")
        
        # Key insight about unchanged weaknesses (only if no big improvements)
        if unchanged_weak and rank_change >= 0 and total_improvement < 30:
            weak_areas = [c['name'] for m, c in unchanged_weak[:2]]
            if weak_areas:
                parts.append(f"• **Key limitation:** {', '.join(weak_areas)} remains weak ({unchanged_weak[0][1]['before']:.0f}th percentile)")
        
        narratives.append('\n'.join(parts))
    
    return narratives


@st.fragment
def show_trade_simulator(simulator):
    """Trade simulation interface"""
    st.header("Trade Impact Simulator")
    st.info(f"Select players to trade. You can use metrics from any season to see impact on **{simulator.current_season}** team rankings.")
    
    available_seasons = simulator.available_seasons
    
    # Initialize session state for trade simulator selections
    if 'trade_season_a' not in st.session_state:
        st.session_state.trade_season_a = available_seasons[0]
    if 'trade_season_b' not in st.session_state:
        st.session_state.trade_season_b = available_seasons[0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Team A")
        
        # Season selector for player A
        season_a = st.selectbox(
            "Season for Player A metrics:", 
            available_seasons, 
            index=available_seasons.index(st.session_state.trade_season_a) if st.session_state.trade_season_a in available_seasons else 0,
            key='trade_sim_season_a'
        )
        st.session_state.trade_season_a = season_a
        
        # Get teams for that season
        teams_a = simulator.get_teams_for_season(season_a)
        
        # Get safe index for team selection
        team_a_idx = 0
        if 'trade_team_a' in st.session_state and st.session_state.trade_team_a in teams_a:
            team_a_idx = teams_a.index(st.session_state.trade_team_a)
        
        team_a = st.selectbox("Select Team:", teams_a, index=team_a_idx, key='trade_sim_team_a')
        st.session_state.trade_team_a = team_a
        
        if team_a:
            players_a = simulator.get_players_for_season(season_a)
            roster_a = players_a[players_a['team'] == team_a].sort_values('icetime', ascending=False)
            player_a_options = [f"{row['name']} ({row['position']}) - {row['icetime']:.0f}min" 
                               for _, row in roster_a.head(25).iterrows()]
            selected_player_a = st.selectbox("Select Player:", player_a_options, key='trade_sim_player_a')
    
    with col2:
        st.subheader("Team B")
        
        # Season selector for player B
        season_b = st.selectbox(
            "Season for Player B metrics:", 
            available_seasons, 
            index=available_seasons.index(st.session_state.trade_season_b) if st.session_state.trade_season_b in available_seasons else 0,
            key='trade_sim_season_b'
        )
        st.session_state.trade_season_b = season_b
        
        # Get teams for that season
        teams_b = simulator.get_teams_for_season(season_b)
        
        # Get safe index for team selection  
        team_b_idx = 0
        if 'trade_team_b' in st.session_state and st.session_state.trade_team_b in teams_b:
            team_b_idx = teams_b.index(st.session_state.trade_team_b)
        
        team_b = st.selectbox("Select Team:", teams_b, index=team_b_idx, key='trade_sim_team_b')
        st.session_state.trade_team_b = team_b
        
        if team_b:
            players_b = simulator.get_players_for_season(season_b)
            roster_b = players_b[players_b['team'] == team_b].sort_values('icetime', ascending=False)
            player_b_options = [f"{row['name']} ({row['position']}) - {row['icetime']:.0f}min" 
                               for _, row in roster_b.head(25).iterrows()]
            selected_player_b = st.selectbox("Select Player:", player_b_options, key='trade_sim_player_b')
    
    st.markdown("---")
    
    if st.button("Simulate Trade", type="primary", use_container_width=True):
        if team_a and team_b and selected_player_a and selected_player_b:
            player_a_name = selected_player_a.split(' (')[0]
            player_b_name = selected_player_b.split(' (')[0]
            
            with st.spinner("Simulating trade..."):
                result = simulator.simulate_trade(
                    team_a, player_a_name, 
                    team_b, player_b_name,
                    season_a=season_a, 
                    season_b=season_b
                )
            
            if result['success']:
                season_note = ""
                if season_a != simulator.current_season or season_b != simulator.current_season:
                    season_note = f" (using {season_a} and {season_b} player metrics)"
                st.success(f"**{result['player_a']['name']}** <-> **{result['player_b']['name']}**{season_note}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(team_a)
                    st.markdown(f"**Loses:** {result['team_a']['loses']} ({season_a} metrics)")
                    st.markdown(f"**Gains:** {result['team_b']['loses']} ({season_b} metrics)")
                    st.metric(f"Rank Change ({result['current_season']})", 
                             f"{result['team_a']['rank_before']} -> {result['team_a']['rank_after']}",
                             delta=result['team_a']['rank_change'],
                             delta_color="inverse")
                    
                    # Show rank context
                    ctx_a = result['team_a'].get('rank_context', {})
                    if ctx_a:
                        if 'team_ahead' in ctx_a:
                            gap = ctx_a['gap_to_ahead']
                            st.caption(f"📈 {gap:.2f} pts behind **{ctx_a['team_ahead']}**")
                        if 'team_behind' in ctx_a:
                            gap = ctx_a['gap_to_behind']
                            st.caption(f"📉 {gap:.2f} pts ahead of **{ctx_a['team_behind']}**")
                
                with col2:
                    st.subheader(team_b)
                    st.markdown(f"**Loses:** {result['team_b']['loses']} ({season_b} metrics)")
                    st.markdown(f"**Gains:** {result['team_a']['loses']} ({season_a} metrics)")
                    st.metric(f"Rank Change ({result['current_season']})",
                             f"{result['team_b']['rank_before']} -> {result['team_b']['rank_after']}",
                             delta=result['team_b']['rank_change'],
                             delta_color="inverse")
                    
                    # Show rank context
                    ctx_b = result['team_b'].get('rank_context', {})
                    if ctx_b:
                        if 'team_ahead' in ctx_b:
                            gap = ctx_b['gap_to_ahead']
                            st.caption(f"📈 {gap:.2f} pts behind **{ctx_b['team_ahead']}**")
                        if 'team_behind' in ctx_b:
                            gap = ctx_b['gap_to_behind']
                            st.caption(f"📉 {gap:.2f} pts ahead of **{ctx_b['team_behind']}**")
                
                # Generate narrative explanations
                st.markdown("---")
                st.markdown("### Trade Analysis")
                
                narratives = generate_trade_narrative(result)
                
                narr_col1, narr_col2 = st.columns(2)
                with narr_col1:
                    st.markdown(narratives[0])
                with narr_col2:
                    st.markdown(narratives[1])
                
                # Show before/after radar charts for each team
                st.markdown("---")
                st.markdown("### Impact on Team Metrics (League Percentiles)")
                st.caption("Blue = Before Trade | Green = After Trade")
                
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    show_trade_impact_radar(
                        result['team_a']['name'],
                        result['team_a']['percentiles_before'],
                        result['team_a']['percentiles_after'],
                        result['current_season']
                    )
                
                with chart_col2:
                    show_trade_impact_radar(
                        result['team_b']['name'],
                        result['team_b']['percentiles_before'],
                        result['team_b']['percentiles_after'],
                        result['current_season']
                    )
                
                # Debug: Show actual metric changes
                with st.expander("📊 Detailed Metric Changes", expanded=False):
                    st.markdown("**Raw metric values before and after trade:**")
                    
                    debug_col1, debug_col2 = st.columns(2)
                    
                    with debug_col1:
                        st.markdown(f"**{team_a}**")
                        for metric in result['team_a']['metrics_before'].keys():
                            before_val = result['team_a']['metrics_before'][metric]
                            after_val = result['team_a']['metrics_after'][metric]
                            change = after_val - before_val
                            pct_before = result['team_a']['percentiles_before'].get(metric, 0)
                            pct_after = result['team_a']['percentiles_after'].get(metric, 0)
                            change_symbol = "↑" if change > 0 else "↓" if change < 0 else "="
                            st.caption(f"{metric}: {before_val:.3f} → {after_val:.3f} ({change_symbol}{abs(change):.3f}) | Pct: {pct_before:.0f}→{pct_after:.0f}")
                    
                    with debug_col2:
                        st.markdown(f"**{team_b}**")
                        for metric in result['team_b']['metrics_before'].keys():
                            before_val = result['team_b']['metrics_before'][metric]
                            after_val = result['team_b']['metrics_after'][metric]
                            change = after_val - before_val
                            pct_before = result['team_b']['percentiles_before'].get(metric, 0)
                            pct_after = result['team_b']['percentiles_after'].get(metric, 0)
                            change_symbol = "↑" if change > 0 else "↓" if change < 0 else "="
                            st.caption(f"{metric}: {before_val:.3f} → {after_val:.3f} ({change_symbol}{abs(change):.3f}) | Pct: {pct_before:.0f}→{pct_after:.0f}")
            else:
                st.error(result['error'])

if __name__ == "__main__":
    main()
