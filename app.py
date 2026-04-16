"""
Sens Friendly Analytics Hub - Streamlit App
Standings Model + Roster Simulation

Self-contained app with authentication for deployment.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit.components.v1 as st_components
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

def _get_data_version():
    """Read the data pipeline timestamp to use as a cache key."""
    from pathlib import Path
    ts_file = Path(__file__).parent / "data" / "last_updated.txt"
    if ts_file.exists():
        return ts_file.read_text().strip()
    return "unknown"

@st.cache_resource
def load_standings_model(_data_version):
    """Load the standings model (cached, invalidates when data updates)"""
    return StandingsModel()

@st.cache_resource
def load_roster_simulator(_standings_model, season=2025, _data_version=None):
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
        data_version = _get_data_version()
        model = load_standings_model(data_version)
        simulator = load_roster_simulator(model, _data_version=data_version)
    
    tab1, tab2, tab3, tab4 = st.tabs(["Team Analysis", "Player Comparison", "Player Risers & Fallers", "Trade Simulator"])
    
    with tab1:
        show_standings_team_analysis(model)
    with tab2:
        show_player_comparison()
    with tab3:
        show_yoy_tracker()
    with tab4:
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
        direction = "BETTER" if variance > 0 else "WORSE"
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
    
    if variance < -3:
        # Underperforming - weakness is likely the culprit
        if weakness_pct < 20:
            explanation = f"Poor {weakness_explanation} ({weakness_pct:.0f}th percentile) is dragging down {team}. Despite solid underlying metrics, they're losing games they should be winning."
        else:
            explanation = f"{team} is underperforming their underlying numbers. Bad luck, close losses, or inconsistency may be factors."
        st.warning(f"**Why the gap?** {explanation}")
    elif variance > 3:
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
    
    if main_team_changed or 'radar_multiselect' not in st.session_state:
        st.session_state.radar_multiselect = new_selection

    selected_teams = st.multiselect(
        "Select teams to compare:",
        teams_for_comparison,
        max_selections=5,
        key='radar_multiselect'
    )
    
    # Store additional teams (everything except the main selected team)
    st.session_state.radar_additional_teams = [t for t in selected_teams if t != team]
    
    if selected_teams:
        # Define a pleasing color palette
        colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A', '#9B5DE5']
        
        fig_spider = go.Figure()
        
        def format_raw_value(metric, raw_val):
            """Format a raw metric value for display"""
            if metric in ('corsipercentage', 'pp_pct', 'pk_pct'):
                return f"{raw_val * 100:.1f}%"
            elif metric in ('save_percentage', 'shooting_percentage'):
                return f"{raw_val:.3f}"
            else:
                return f"{raw_val:.1f}"
        
        for idx, selected_team in enumerate(selected_teams):
            team_analysis = model.analyze_team_prediction(selected_team, season)
            if team_analysis:
                display_names = []
                percentiles = []
                hover_texts = []
                label_texts = []
                
                for metric, data in team_analysis['metrics'].items():
                    name = METRIC_DISPLAY_NAMES.get(metric, metric.replace('_', ' ').title())
                    display_names.append(name)
                    percentiles.append(data['percentile'])
                    raw_str = format_raw_value(metric, data['value'])
                    hover_texts.append(f"<b>{name}</b><br>{data['percentile']:.0f}% ({raw_str})")
                    label_texts.append(f"{data['percentile']:.0f}% ({raw_str})")
                
                # Close the polygon
                display_names.append(display_names[0])
                percentiles.append(percentiles[0])
                hover_texts.append(hover_texts[0])
                label_texts.append(label_texts[0])
                
                team_color = colors[idx % len(colors)]
                
                fig_spider.add_trace(go.Scatterpolar(
                    r=percentiles,
                    theta=display_names,
                    fill='toself',
                    name=selected_team,
                    legendgroup=selected_team,
                    line=dict(width=3, color=team_color),
                    fillcolor=team_color,
                    opacity=0.4,
                    text=hover_texts,
                    hovertemplate='%{text}<extra>' + selected_team + '</extra>',
                    textposition='top center',
                    textfont=dict(size=15, color=team_color),
                ))
                
                # Separate scatter trace for labels (avoids label on the closing point)
                fig_spider.add_trace(go.Scatterpolar(
                    r=percentiles[:-1],
                    theta=display_names[:-1],
                    mode='text',
                    text=label_texts[:-1],
                    textposition='top center',
                    textfont=dict(size=15, color=team_color),
                    showlegend=False,
                    legendgroup=selected_team,
                    hoverinfo='skip',
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
                y=-0.12,
                xanchor='center',
                x=0.5,
                font=dict(size=15)
            ),
            height=900,
            margin=dict(t=60, b=120, l=120, r=120),
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
    
    # NHL logo URL mapping (shared across sections)
    TEAM_LOGO_ABBREV = {
        'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
        'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
        'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ',
        'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
        'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
        'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD',
        'New York Islanders': 'NYI', 'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
        'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS',
        'Seattle Kraken': 'SEA', 'St. Louis Blues': 'STL', 'Tampa Bay Lightning': 'TBL',
        'Toronto Maple Leafs': 'TOR', 'Utah Mammoth': 'UTA', 'Utah Hockey Club': 'UTA',
        'Vancouver Canucks': 'VAN', 'Vegas Golden Knights': 'VGK', 'Washington Capitals': 'WSH',
        'Winnipeg Jets': 'WPG',
    }

    # ==================== WHAT-IF SIMULATOR ====================
    st.markdown("---")
    st.subheader("What-If Simulator")
    st.caption(f"Adjust {team}'s metrics to see how their predicted ranking would change.")
    
    what_if_metrics = {k: v for k, v in METRIC_DISPLAY_NAMES.items() if k in model.metrics_list}
    what_if_keys = list(what_if_metrics.keys())
    
    def format_whatif_value(metric, val):
        if metric in ('corsipercentage', 'pp_pct', 'pk_pct'):
            return f"{val * 100:.1f}%"
        elif metric in ('save_percentage', 'shooting_percentage'):
            return f"{val:.3f}"
        else:
            return f"{val:.1f}"
    
    if 'whatif_count' not in st.session_state:
        st.session_state.whatif_count = 1
    
    def add_metric():
        if st.session_state.whatif_count < len(what_if_keys):
            st.session_state.whatif_count += 1
    
    def reset_whatif():
        keys_to_remove = [k for k in st.session_state if k.startswith('whatif_')]
        for key in keys_to_remove:
            st.session_state.pop(key, None)
        st.session_state.whatif_count = 1
    
    def remove_metric(idx):
        count = st.session_state.whatif_count
        for k in list(st.session_state):
            if k.startswith(f'whatif_metric_{idx}') or k.startswith(f'whatif_slider_{idx}'):
                st.session_state.pop(k, None)
        for j in range(idx + 1, count):
            for prefix in ['whatif_metric_', 'whatif_slider_']:
                for k in list(st.session_state):
                    if k.startswith(f'{prefix}{j}'):
                        st.session_state.pop(k, None)
        st.session_state.whatif_count = count - 1

    @st.fragment
    def whatif_fragment():
        metric_overrides = {}
        used_metrics = []
        
        for i in range(st.session_state.whatif_count):
            available = [m for m in what_if_keys if m not in used_metrics]
            if not available:
                break
            
            col_metric, col_slider, col_remove = st.columns([1, 2, 0.15])
            
            with col_metric:
                selected = st.selectbox(
                    "Metric" if i == 0 else f"Metric {i + 1}",
                    available,
                    format_func=lambda x: what_if_metrics[x],
                    key=f'whatif_metric_{i}'
                )
            
            current_info = analysis['metrics'].get(selected, {})
            current_pctl = int(round(current_info.get('percentile', 50)))
            current_val = current_info.get('value', 0)
            
            with col_slider:
                target_pctl = st.slider(
                    f"Target percentile (current: {current_pctl}th — {format_whatif_value(selected, current_val)})",
                    min_value=0,
                    max_value=100,
                    value=current_pctl,
                    step=1,
                    key=f'whatif_slider_{i}_{selected}_{team}'
                )
            
            with col_remove:
                if i > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("✕", key=f'whatif_remove_{i}', on_click=remove_metric, args=(i,))
            
            metric_overrides[selected] = target_pctl
            used_metrics.append(selected)
        
        col_add, col_reset, _ = st.columns([1, 1, 3])
        with col_add:
            st.button("+ Add Metric", on_click=add_metric,
                       disabled=st.session_state.whatif_count >= len(what_if_keys))
        with col_reset:
            if st.session_state.whatif_count > 1:
                st.button("Reset", on_click=reset_whatif)
        
        result = model.what_if_prediction(team, season, metric_overrides)
        
        if result:
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Predicted Rank", result['original_predicted_rank'])
            with col2:
                rank_delta = result['rank_change']
                st.metric(
                    "What-If Predicted Rank",
                    result['new_predicted_rank'],
                    delta=f"{rank_delta:+d} spots" if rank_delta != 0 else "No change",
                    delta_color="normal"
                )
            with col3:
                score_delta = result['original_score'] - result['new_score']
                st.metric(
                    "Model Score",
                    f"{result['new_score']:.1f}",
                    delta=f"{score_delta:+.1f} (from {result['original_score']:.1f})",
                    delta_color="normal",
                    help="Raw model output (lower = better). Rank only changes when this crosses another team's score."
                )
            
            # Build current vs what-if radar chart
            current_percentiles = []
            whatif_percentiles = []
            radar_names = []
            current_hover = []
            whatif_hover = []
            current_labels = []
            whatif_labels = []
            
            team_analysis = model.analyze_team_prediction(team, season)
            if team_analysis:
                for metric_key, data in team_analysis['metrics'].items():
                    name = METRIC_DISPLAY_NAMES.get(metric_key, metric_key)
                    radar_names.append(name)
                    current_percentiles.append(data['percentile'])
                    raw_str = format_whatif_value(metric_key, data['value'])
                    current_hover.append(f"<b>{name}</b><br>{data['percentile']:.0f}% ({raw_str})")
                    current_labels.append(f"{data['percentile']:.0f}% ({raw_str})")
                    
                    if metric_key in metric_overrides:
                        wi_pctl = float(metric_overrides[metric_key])
                        whatif_percentiles.append(wi_pctl)
                        whatif_hover.append(f"<b>{name}</b><br>{wi_pctl:.0f}% (adjusted)")
                        whatif_labels.append(f"{wi_pctl:.0f}%")
                    else:
                        whatif_percentiles.append(data['percentile'])
                        whatif_hover.append(f"<b>{name}</b><br>{data['percentile']:.0f}% ({raw_str})")
                        whatif_labels.append(f"{data['percentile']:.0f}% ({raw_str})")
                
                radar_names_closed = radar_names + [radar_names[0]]
                current_closed = current_percentiles + [current_percentiles[0]]
                whatif_closed = whatif_percentiles + [whatif_percentiles[0]]
                current_hover_closed = current_hover + [current_hover[0]]
                whatif_hover_closed = whatif_hover + [whatif_hover[0]]
                current_labels_closed = current_labels + [current_labels[0]]
                whatif_labels_closed = whatif_labels + [whatif_labels[0]]
                
                has_changes = any(abs(c - w) > 0.5 for c, w in zip(current_percentiles, whatif_percentiles))
                
                fig_whatif = go.Figure()
                
                # Current trace
                fig_whatif.add_trace(go.Scatterpolar(
                    r=current_closed,
                    theta=radar_names_closed,
                    fill='toself',
                    name='Current',
                    legendgroup='Current',
                    line=dict(width=3, color='#E63946'),
                    fillcolor='#E63946',
                    opacity=0.4,
                    text=current_hover_closed,
                    hovertemplate='%{text}<extra>Current</extra>',
                    textposition='top center',
                    textfont=dict(size=15, color='#E63946'),
                ))
                
                if not has_changes:
                    # Labels for current only
                    fig_whatif.add_trace(go.Scatterpolar(
                        r=current_closed[:-1],
                        theta=radar_names_closed[:-1],
                        mode='text',
                        text=current_labels,
                        textposition='top center',
                        textfont=dict(size=15, color='#E63946'),
                        showlegend=False,
                        legendgroup='Current',
                        hoverinfo='skip',
                    ))
                
                if has_changes:
                    # What-if trace
                    fig_whatif.add_trace(go.Scatterpolar(
                        r=whatif_closed,
                        theta=radar_names_closed,
                        fill='toself',
                        name='What-If',
                        legendgroup='What-If',
                        line=dict(width=3, color='#457B9D'),
                        fillcolor='#457B9D',
                        opacity=0.4,
                        text=whatif_hover_closed,
                        hovertemplate='%{text}<extra>What-If</extra>',
                        textposition='top center',
                        textfont=dict(size=15, color='#457B9D'),
                    ))
                    
                    # Labels for what-if
                    fig_whatif.add_trace(go.Scatterpolar(
                        r=whatif_closed[:-1],
                        theta=radar_names_closed[:-1],
                        mode='text',
                        text=whatif_labels,
                        textposition='top center',
                        textfont=dict(size=15, color='#457B9D'),
                        showlegend=False,
                        legendgroup='What-If',
                        hoverinfo='skip',
                    ))
                
                season_display = f"{season - 1}-{str(season)[-2:]}"
                
                fig_whatif.update_layout(
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
                        y=-0.12,
                        xanchor='center',
                        x=0.5,
                        font=dict(size=15)
                    ),
                    height=900,
                    margin=dict(t=60, b=120, l=120, r=120),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    dragmode=False,
                )
                
                st.plotly_chart(fig_whatif, use_container_width=True)
                st.caption(f"*{team} — {season_display}*")
            
            if abs(result['rank_change']) > 0:
                moved = result['all_teams']
                moved_teams = [t for t in moved if t['original_rank'] != t['new_rank']]
                moved_teams.sort(key=lambda t: t['new_rank'])
                
                st.markdown(f"**League Impact** — {len(moved_teams)} teams affected")
                impact_rows = []
                for t in moved_teams:
                    delta = t['original_rank'] - t['new_rank']
                    abbrev = TEAM_LOGO_ABBREV.get(t['team'], 'NHL')
                    logo_url = f"https://assets.nhle.com/logos/nhl/svg/{abbrev}_dark.svg"
                    impact_rows.append({
                        'Logo': logo_url,
                        'Team': t['team'],
                        'Before': t['original_rank'],
                        'After': t['new_rank'],
                        'Change': f"{delta:+d}",
                    })
                impact_df = pd.DataFrame(impact_rows)
                st.dataframe(
                    impact_df,
                    column_config={
                        'Logo': st.column_config.ImageColumn('', width='small'),
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=min(len(impact_df) * 38 + 40, 600)
                )
    
    whatif_fragment()
    
    # ==================== LEAGUE-WIDE STANDINGS TABLE ====================
    st.markdown("---")
    st.subheader("League-Wide Standings & Metrics")
    st.caption("Click any column header to sort. Metric columns show percentile (actual value).")
    
    # Build table data from model results
    season_data = model.df_results[model.df_results['season'] == season].copy()
    
    if not season_data.empty:
        all_metrics = list(METRIC_DISPLAY_NAMES.keys())
        
        table_rows = []
        for _, row in season_data.iterrows():
            team_name = row['team_full']
            abbrev = TEAM_LOGO_ABBREV.get(team_name, 'NHL')
            logo_url = f"https://assets.nhle.com/logos/nhl/svg/{abbrev}_dark.svg"
            table_row = {
                'Logo': logo_url,
                'Team': team_name,
                'Pred Rank': int(row['predicted_rank_placement']),
                'Actual Rank': int(row['team_rank']),
                'Delta': int(row['ranking_variance']),
            }
            for metric in all_metrics:
                display_name = METRIC_DISPLAY_NAMES[metric]
                pct_col = f'{metric}_percentile'
                if metric in row.index and pct_col in row.index:
                    pct_val = int(round(row[pct_col]))
                    raw_val = row[metric]
                    if metric in ('corsipercentage', 'pp_pct', 'pk_pct'):
                        raw_str = f"{raw_val * 100:.1f}%"
                    elif metric in ('save_percentage', 'shooting_percentage'):
                        raw_str = f"{raw_val:.3f}"
                    else:
                        raw_str = f"{raw_val:.1f}"
                    # Right-align percentile with leading non-breaking spaces for correct string sorting
                    pct_str = str(pct_val).rjust(3, '\u2007')
                    table_row[display_name] = f"{pct_str}% ({raw_str})"
            table_rows.append(table_row)
        
        table_df = pd.DataFrame(table_rows).sort_values('Pred Rank').reset_index(drop=True)
        
        st.dataframe(
            table_df,
            column_config={
                'Logo': st.column_config.ImageColumn('', width='small'),
            },
            use_container_width=True,
            hide_index=True,
            height=min(len(table_df) * 38 + 40, 1200)
        )
    
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
    
    # Player metrics: balanced across offense, defense, two-way, and physical
    PLAYER_METRICS = {
        'gameScore': {'name': 'Game Score', 'desc': 'Composite game impact rating (5v5)', 'per60': False, 'category': 'Overall'},
        'I_F_xGoals_per60': {'name': 'xGoals/60', 'desc': 'Expected goals generated per 60 min', 'per60': True, 'raw': 'I_F_xGoals', 'category': 'Offense'},
        'I_F_points_per60': {'name': 'Points/60', 'desc': '5v5 points per 60 minutes', 'per60': True, 'raw': 'I_F_points', 'category': 'Offense'},
        'I_F_highDangerShots_per60': {'name': 'HD Shots/60', 'desc': 'High-danger shots per 60 min', 'per60': True, 'raw': 'I_F_highDangerShots', 'category': 'Offense'},
        'I_F_hits_per60': {'name': 'Hits/60', 'desc': 'Hits per 60 minutes', 'per60': True, 'raw': 'I_F_hits', 'category': 'Physical'},
        'takeaway_giveaway_ratio': {'name': 'TA/GA Ratio', 'desc': 'Takeaways per giveaway — puck management', 'per60': False, 'category': 'Defense'},
        'onIce_xGA_per60': {'name': 'On-Ice xGA/60', 'desc': 'Expected goals against per 60 min when on ice (lower = better)', 'per60': True, 'raw': 'OnIce_A_xGoals', 'inverted': True, 'category': 'Defense'},
        'onIce_hdA_per60': {'name': 'On-Ice HDA/60', 'desc': 'High-danger chances against per 60 min (lower = better)', 'per60': True, 'raw': 'OnIce_A_highDangerShots', 'inverted': True, 'category': 'Defense'},
        'onIce_corsiPercentage': {'name': 'On-Ice Corsi%', 'desc': 'Shot attempt share when on ice', 'per60': False, 'category': 'Two-Way'},
        'onIce_xGoalsPercentage': {'name': 'On-Ice xG%', 'desc': 'Expected goals share when on ice', 'per60': False, 'category': 'Two-Way'},
    }
    
    # Calculate per-60 and derived metrics on 5on5 data
    for metric_key, metric_info in PLAYER_METRICS.items():
        if metric_info.get('per60') and 'raw' in metric_info:
            raw_col = metric_info['raw']
            if raw_col in player_df_5on5.columns:
                player_df_5on5[metric_key] = (player_df_5on5[raw_col] / player_df_5on5['icetime']) * 3600
    
    # Takeaway/giveaway ratio (avoid division by zero)
    if 'I_F_takeaways' in player_df_5on5.columns and 'I_F_giveaways' in player_df_5on5.columns:
        player_df_5on5['takeaway_giveaway_ratio'] = (
            player_df_5on5['I_F_takeaways'] / player_df_5on5['I_F_giveaways'].clip(lower=1)
        )
    
    # Add position group column for position-based percentiles
    player_df_5on5['pos_group'] = player_df_5on5['position'].map(
        {'C': 'F', 'L': 'F', 'R': 'F', 'D': 'D'}
    )
    
    # Get available seasons from all-situations data (for selection)
    seasons = sorted(player_df_all['season'].unique(), reverse=True)
    
    st.markdown("---")
    st.subheader("Select Players to Compare")
    
    # Helper to get player index (preserves selection, defaults to OTT)
    def get_player_index(players_list, stored_key, default=None, default_index=0):
        if stored_key in st.session_state:
            stored_name = st.session_state[stored_key]
            if stored_name in players_list:
                return players_list.index(stored_name)
        if default and default in players_list:
            return players_list.index(default)
        return min(default_index, len(players_list) - 1)
    
    # Player 1 selection
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Player 1**")
        season1 = st.selectbox("Season", seasons, key='player1_season')
        
        # Get teams for this season
        teams1 = sorted(player_df_all[player_df_all['season'] == season1]['team'].unique())
        team1_idx = get_player_index(teams1, 'player1_team', default='OTT')
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
        team2_idx = get_player_index(teams2, 'player2_team', default='OTT')
        team2 = st.selectbox("Team", teams2, index=team2_idx, key='player2_team')
        
        players2 = sorted(player_df_all[(player_df_all['season'] == season2) & (player_df_all['team'] == team2)]['name'].unique())
        player2_idx = get_player_index(players2, 'player2_name', default_index=1)
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
        
        # Calculate position-based percentiles (F vs D) with support for inverted metrics
        def get_player_percentiles(player_row, season, metrics):
            pos = player_row.get('pos_group', 'F')
            all_skaters = player_df_5on5[player_df_5on5['season'] == season]
            pos_peers = all_skaters[all_skaters['pos_group'] == pos]
            percentiles = {}
            for metric_key in metrics:
                peers = all_skaters if metric_key == 'gameScore' else pos_peers
                if metric_key in peers.columns and metric_key in player_row.index:
                    val = player_row[metric_key]
                    if PLAYER_METRICS[metric_key].get('inverted'):
                        pct = (peers[metric_key] > val).mean() * 100
                    else:
                        pct = (peers[metric_key] < val).mean() * 100
                    percentiles[metric_key] = pct
            return percentiles, pos
        
        metric_keys = [k for k in PLAYER_METRICS.keys() if k in player_df_5on5.columns]
        
        # Get percentiles (only if 5on5 data exists)
        p1_percentiles, p1_pos = {}, 'F'
        p2_percentiles, p2_pos = {}, 'F'
        if not p1_5on5.empty:
            p1_percentiles, p1_pos = get_player_percentiles(p1_5on5.iloc[0], season1, metric_keys)
        if not p2_5on5.empty:
            p2_percentiles, p2_pos = get_player_percentiles(p2_5on5.iloc[0], season2, metric_keys)
        
        # Display key stats (from ALL-SITUATIONS data = total stats) - compact card layout
        st.markdown("---")
        
        # Compact player comparison cards
        def calc_toi_gp(row):
            gp = int(row.get('games_played', 0))
            icetime = float(row.get('icetime', 0))
            if gp > 0:
                avg_min = icetime / 60 / gp
                mm = int(avg_min)
                ss = int(round((avg_min - mm) * 60))
                return f"{mm}:{ss:02d}"
            return "—"

        p1_gp = int(p1_all_row['games_played'])
        p1_pts = int(p1_all_row.get('I_F_points', 0))
        p1_g = int(p1_all_row.get('I_F_goals', 0))
        p1_a = p1_pts - p1_g
        p1_hits = int(p1_all_row.get('I_F_hits', 0))
        p1_blk = int(p1_all_row.get('shotsBlockedByPlayer', 0))
        p1_toi = calc_toi_gp(p1_all_row)
        
        p2_gp = int(p2_all_row['games_played'])
        p2_pts = int(p2_all_row.get('I_F_points', 0))
        p2_g = int(p2_all_row.get('I_F_goals', 0))
        p2_a = p2_pts - p2_g
        p2_hits = int(p2_all_row.get('I_F_hits', 0))
        p2_blk = int(p2_all_row.get('shotsBlockedByPlayer', 0))
        p2_toi = calc_toi_gp(p2_all_row)
        
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
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p1_toi}</span> <span style="color: gray;">TOI/GP</span></div>
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
                    <div><span style="font-size: 1.4em; font-weight: bold;">{p2_toi}</span> <span style="color: gray;">TOI/GP</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Build radar chart
        st.markdown("---")
        st.subheader("Performance Radar (Position Percentiles)")
        pos_labels = {'F': 'Forwards', 'D': 'Defensemen'}
        p1_pos_label = pos_labels.get(p1_pos, 'All')
        p2_pos_label = pos_labels.get(p2_pos, 'All')
        if p1_pos == p2_pos:
            st.caption(f"*5v5 metrics — percentiles vs. other {p1_pos_label}*")
        else:
            st.caption(f"*5v5 metrics — {player1_name} vs. {p1_pos_label}, {player2_name} vs. {p2_pos_label}*")
        
        display_names = [PLAYER_METRICS[k]['name'] for k in metric_keys]
        p1_values = [p1_percentiles.get(k, 50) for k in metric_keys]
        p2_values = [p2_percentiles.get(k, 50) for k in metric_keys]
        
        # Close the polygon
        display_names_closed = display_names + [display_names[0]]
        p1_closed = p1_values + [p1_values[0]]
        p2_closed = p2_values + [p2_values[0]]
        
        fig = go.Figure()
        
        # Build label texts with percentile% (raw value)
        def format_player_raw(metric_key, player_row):
            if metric_key in player_row.index:
                val = player_row[metric_key]
                if 'Percentage' in metric_key or 'percentage' in metric_key:
                    return f"{val:.1f}%"
                elif metric_key == 'takeaway_giveaway_ratio':
                    return f"{val:.2f}x"
                else:
                    return f"{val:.2f}"
            return ""
        
        p1_labels = []
        p2_labels = []
        p1_hovers = []
        p2_hovers = []
        for k in metric_keys:
            name = PLAYER_METRICS[k]['name']
            p1_pct = p1_percentiles.get(k, 50)
            p2_pct = p2_percentiles.get(k, 50)
            p1_raw = format_player_raw(k, p1_5on5.iloc[0]) if not p1_5on5.empty else ""
            p2_raw = format_player_raw(k, p2_5on5.iloc[0]) if not p2_5on5.empty else ""
            p1_labels.append(f"{p1_pct:.0f}% ({p1_raw})")
            p2_labels.append(f"{p2_pct:.0f}% ({p2_raw})")
            p1_hovers.append(f"<b>{name}</b><br>{p1_pct:.0f}% ({p1_raw})")
            p2_hovers.append(f"<b>{name}</b><br>{p2_pct:.0f}% ({p2_raw})")
        
        p1_labels_closed = p1_labels + [p1_labels[0]]
        p2_labels_closed = p2_labels + [p2_labels[0]]
        p1_hovers_closed = p1_hovers + [p1_hovers[0]]
        p2_hovers_closed = p2_hovers + [p2_hovers[0]]
        
        # Player 1
        p1_legend = f"{player1_name} ({season1})"
        fig.add_trace(go.Scatterpolar(
            r=p1_closed,
            theta=display_names_closed,
            fill='toself',
            name=p1_legend,
            legendgroup=p1_legend,
            line=dict(width=3, color='#E63946'),
            fillcolor='#E63946',
            opacity=0.4,
            text=p1_hovers_closed,
            hovertemplate='%{text}<extra>' + f'{player1_name}' + '</extra>',
            textfont=dict(size=15, color='#E63946'),
        ))
        fig.add_trace(go.Scatterpolar(
            r=p1_values,
            theta=display_names,
            mode='text',
            text=p1_labels,
            textposition='top center',
            textfont=dict(size=15, color='#E63946'),
            showlegend=False,
            legendgroup=p1_legend,
            hoverinfo='skip',
        ))
        
        # Player 2
        p2_legend = f"{player2_name} ({season2})"
        fig.add_trace(go.Scatterpolar(
            r=p2_closed,
            theta=display_names_closed,
            fill='toself',
            name=p2_legend,
            legendgroup=p2_legend,
            line=dict(width=3, color='#457B9D'),
            fillcolor='#457B9D',
            opacity=0.4,
            text=p2_hovers_closed,
            hovertemplate='%{text}<extra>' + f'{player2_name}' + '</extra>',
            textfont=dict(size=15, color='#457B9D'),
        ))
        fig.add_trace(go.Scatterpolar(
            r=p2_values,
            theta=display_names,
            mode='text',
            text=p2_labels,
            textposition='bottom center',
            textfont=dict(size=15, color='#457B9D'),
            showlegend=False,
            legendgroup=p2_legend,
            hoverinfo='skip',
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
                yanchor='top',
                y=-0.05,
                xanchor='center',
                x=0.5,
                font=dict(size=15)
            ),
            height=1000,
            margin=dict(t=140, b=140, l=140, r=140),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            dragmode=False,
            hovermode='closest'
        )
        
        # Render radar chart with category ring via embedded HTML component
        _chart_inner = pio.to_html(fig, full_html=False, include_plotlyjs='cdn',
                                   config={'displayModeBar': False, 'scrollZoom': False, 'responsive': True})
        _ring_before = """<!DOCTYPE html><html><head>
<style>
html, body { margin: 0; padding: 0; background: #0E1117; }
#wrapper { position: relative; width: 100%; }
#ring-svg {
  position: absolute; pointer-events: none; display: none; z-index: 10;
  overflow: visible;
}
.cat-label {
  position: absolute;
  font-family: "Source Sans Pro", sans-serif;
  font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
  text-transform: uppercase; white-space: nowrap;
  pointer-events: none; transform: translate(-50%, -50%);
  display: none; z-index: 11;
}
</style></head><body>
<div id="wrapper">
  <svg id="ring-svg" xmlns="http://www.w3.org/2000/svg"></svg>
  <div class="cat-label" id="label-offense" style="color:#E63946;">OFFENSE</div>
  <div class="cat-label" id="label-grit" style="color:#E9C46A;">GRIT</div>
  <div class="cat-label" id="label-defense" style="color:#457B9D;">DEFENSE</div>
  <div class="cat-label" id="label-twoway" style="color:#2A9D8F;">TWO-WAY</div>
"""
        _ring_after = """</div>
<script>
function positionRing() {
  var ticks = document.querySelectorAll('.angularaxistick text');
  if (!ticks.length) return false;
  var wr = document.getElementById('wrapper');
  var wrR = wr.getBoundingClientRect();
  var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  ticks.forEach(function(t) {
    var r = t.getBoundingClientRect();
    minX = Math.min(minX, r.left);  maxX = Math.max(maxX, r.right);
    minY = Math.min(minY, r.top);   maxY = Math.max(maxY, r.bottom);
  });
  var cx = ((minX + maxX) / 2) - wrR.left;
  var cy = ((minY + maxY) / 2) - wrR.top;
  var maxR = 0;
  ticks.forEach(function(t) {
    var r = t.getBoundingClientRect();
    [[r.left, r.top], [r.right, r.top], [r.left, r.bottom], [r.right, r.bottom]]
      .forEach(function(c) {
        var d = Math.sqrt(Math.pow(c[0] - wrR.left - cx, 2) + Math.pow(c[1] - wrR.top - cy, 2));
        maxR = Math.max(maxR, d);
      });
  });
  var pad = 18;
  var arcR = maxR + pad;
  var sw = 5;
  var svg = document.getElementById('ring-svg');
  svg.innerHTML = '';
  var svgSz = (arcR + sw) * 2;
  svg.setAttribute('width', svgSz);
  svg.setAttribute('height', svgSz);
  svg.style.left = (cx - svgSz / 2) + 'px';
  svg.style.top = (cy - svgSz / 2) + 'px';
  svg.style.display = 'block';
  var sc = svgSz / 2;
  var NS = 'http://www.w3.org/2000/svg';
  [{s:324,sp:144,c:'#E63946'},{s:108,sp:72,c:'#2A9D8F'},
   {s:180,sp:108,c:'#457B9D'},{s:288,sp:36,c:'#E9C46A'}]
    .forEach(function(seg) {
      var a1 = (seg.s - 90) * Math.PI / 180;
      var a2 = (seg.s + seg.sp - 90) * Math.PI / 180;
      var x1 = sc + arcR * Math.cos(a1), y1 = sc + arcR * Math.sin(a1);
      var x2 = sc + arcR * Math.cos(a2), y2 = sc + arcR * Math.sin(a2);
      var la = seg.sp > 180 ? 1 : 0;
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d','M '+x1+' '+y1+' A '+arcR+' '+arcR+' 0 '+la+' 1 '+x2+' '+y2);
      p.setAttribute('fill','none');
      p.setAttribute('stroke', seg.c);
      p.setAttribute('stroke-opacity', '0.5');
      p.setAttribute('stroke-width', sw);
      svg.appendChild(p);
    });
  var lr = arcR + 28;
  [{id:'label-offense',a:36},{id:'label-grit',a:306},
   {id:'label-defense',a:234},{id:'label-twoway',a:144}]
    .forEach(function(l) {
      var el = document.getElementById(l.id);
      var rad = l.a * Math.PI / 180;
      el.style.left = (cx + lr * Math.sin(rad)) + 'px';
      el.style.top = (cy - lr * Math.cos(rad)) + 'px';
      el.style.display = 'block';
    });
  return true;
}
function relayoutPlot() {
  var gd = document.querySelector('.plotly-graph-div');
  if (gd && window.Plotly) {
    Plotly.Plots.resize(gd);
    Plotly.relayout(gd, {});
  }
}
setTimeout(function() {
  var att = 0, iv = setInterval(function() {
    if (positionRing() || att > 30) clearInterval(iv);
    att++;
  }, 200);
}, 500);
document.fonts.ready.then(function() { setTimeout(function() { relayoutPlot(); positionRing(); }, 300); });
[1500, 3000].forEach(function(ms) { setTimeout(function() { relayoutPlot(); positionRing(); }, ms); });
window.addEventListener('resize', function() { setTimeout(function() { relayoutPlot(); positionRing(); }, 300); });
</script></body></html>"""
        st_components.html(_ring_before + _chart_inner + _ring_after, height=1100, scrolling=False)
        
        # Percentile guide
        st.markdown("""
        <div style="text-align: center; padding: 10px; background: rgba(128,128,128,0.1); border-radius: 8px; margin-bottom: 20px;">
            <span style="color: #E63946;">●</span> <b>0-25%</b> Poor &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #E9C46A;">●</span> <b>25-50%</b> Below Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #457B9D;">●</span> <b>50-75%</b> Above Avg &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #2A9D8F;">●</span> <b>75-100%</b> Excellent
        </div>
        """, unsafe_allow_html=True)
        
        # Metric definitions grouped by category
        with st.expander("📊 What do these metrics mean?", expanded=False):
            categories = {}
            for k in metric_keys:
                cat = PLAYER_METRICS[k].get('category', 'Other')
                if cat not in categories:
                    categories[cat] = []
                inv_note = " *(inverted: lower raw value = higher percentile)*" if PLAYER_METRICS[k].get('inverted') else ""
                categories[cat].append((PLAYER_METRICS[k]['name'], PLAYER_METRICS[k]['desc'] + inv_note))
            
            for cat_name, items in categories.items():
                st.markdown(f"**{cat_name}**")
                for name, desc in items:
                    st.caption(f"  **{name}** — {desc}")
                st.markdown("")
            
            st.caption("*Percentiles are calculated within position group (Forwards vs. Defensemen) for fairer comparison.*")


# ==================== YOY TRACKER ====================

@st.fragment
def show_yoy_tracker():
    """Year-over-year player performance tracker with weighted composite score"""
    st.header("Year-over-Year Performance Tracker")
    st.caption("Identify players who have improved or regressed the most between seasons")

    try:
        player_df_5on5 = load_player_data()
        player_df_all = load_player_data_all()
    except FileNotFoundError as e:
        st.error(f"Player data not found. Run the data pipeline first: {e}")
        return

    player_df_5on5 = player_df_5on5[player_df_5on5['games_played'] >= 20].copy()

    # --- Composite methodology (preserved for potential revert) ---
    # COMPOSITE_METRICS = {
    #     'gameScore': 0.30,
    #     'I_F_xGoals_per60': 0.20,
    #     'I_F_points_per60': 0.20,
    #     'onIce_xGoalsPercentage': 0.20,
    #     'onIce_corsiPercentage': 0.10,
    # }
    # def compute_composite(percentiles):
    #     score = 0.0
    #     total_weight = 0.0
    #     for k in composite_keys:
    #         if k in percentiles:
    #             score += percentiles[k] * COMPOSITE_METRICS[k]
    #             total_weight += COMPOSITE_METRICS[k]
    #     if total_weight > 0:
    #         return score / total_weight
    #     return 50.0
    # --- End composite methodology ---

    ALL_DISPLAY_METRICS = {
        'gameScore': {'name': 'Game Score', 'inverted': False, 'fmt': '.2f'},
        'I_F_xGoals_per60': {'name': 'xGoals/60', 'inverted': False, 'raw': 'I_F_xGoals', 'fmt': '.2f'},
        'I_F_points_per60': {'name': 'Points/60', 'inverted': False, 'raw': 'I_F_points', 'fmt': '.2f'},
        'I_F_highDangerShots_per60': {'name': 'HD Shots/60', 'inverted': False, 'raw': 'I_F_highDangerShots', 'fmt': '.2f'},
        'I_F_hits_per60': {'name': 'Hits/60', 'inverted': False, 'raw': 'I_F_hits', 'fmt': '.2f'},
        'takeaway_giveaway_ratio': {'name': 'TA/GA Ratio', 'inverted': False, 'fmt': '.2fx'},
        'onIce_xGA_per60': {'name': 'On-Ice xGA/60', 'inverted': True, 'raw': 'OnIce_A_xGoals', 'fmt': '.2f'},
        'onIce_hdA_per60': {'name': 'On-Ice HDA/60', 'inverted': True, 'raw': 'OnIce_A_highDangerShots', 'fmt': '.2f'},
        'onIce_corsiPercentage': {'name': 'On-Ice Corsi%', 'inverted': False, 'fmt': '.1f%'},
        'onIce_xGoalsPercentage': {'name': 'On-Ice xG%', 'inverted': False, 'fmt': '.1f%'},
    }

    for metric_key, info in ALL_DISPLAY_METRICS.items():
        if info.get('raw') and info['raw'] in player_df_5on5.columns:
            player_df_5on5[metric_key] = (player_df_5on5[info['raw']] / player_df_5on5['icetime']) * 3600

    if 'I_F_takeaways' in player_df_5on5.columns and 'I_F_giveaways' in player_df_5on5.columns:
        player_df_5on5['takeaway_giveaway_ratio'] = (
            player_df_5on5['I_F_takeaways'] / player_df_5on5['I_F_giveaways'].clip(lower=1)
        )

    player_df_5on5['pos_group'] = player_df_5on5['position'].map(
        {'C': 'F', 'L': 'F', 'R': 'F', 'D': 'D'}
    )

    metric_keys = [k for k in ALL_DISPLAY_METRICS.keys() if k in player_df_5on5.columns]

    def get_percentile(val, series, inverted=False):
        if inverted:
            return float((series > val).mean() * 100)
        return float((series < val).mean() * 100)

    def compute_player_percentiles(player_row, season, pos_group):
        all_skaters = player_df_5on5[player_df_5on5['season'] == season]
        pos_peers = all_skaters[all_skaters['pos_group'] == pos_group]
        pcts = {}
        for k in metric_keys:
            peers = all_skaters if k == 'gameScore' else pos_peers
            if k in player_row.index and k in peers.columns:
                pcts[k] = get_percentile(player_row[k], peers[k], ALL_DISPLAY_METRICS[k].get('inverted', False))
        return pcts

    def format_raw(metric_key, val):
        fmt = ALL_DISPLAY_METRICS[metric_key].get('fmt', '.2f')
        if fmt.endswith('x'):
            return f"{val:{fmt[:-1]}}x"
        elif fmt.endswith('%'):
            return f"{val:{fmt[:-1]}}%"
        return f"{val:{fmt}}"

    seasons = sorted(player_df_5on5['season'].unique(), reverse=True)
    seasons_with_prior = [s for s in seasons if (s - 1) in player_df_5on5['season'].unique()]

    if not seasons_with_prior:
        st.warning("Need at least two consecutive seasons to compare.")
        return

    st.markdown("---")

    col_season, col_pos = st.columns([1, 1])
    with col_season:
        selected_season = st.selectbox(
            "Compare season",
            seasons_with_prior,
            format_func=lambda s: f"{s} vs {s - 1}",
            key='yoy_season'
        )
    with col_pos:
        pos_filter = st.selectbox("Position", ["All Skaters", "Forwards", "Defensemen"], key='yoy_pos')

    prior_season = selected_season - 1
    pos_map = {"All Skaters": None, "Forwards": "F", "Defensemen": "D"}
    pos_val = pos_map[pos_filter]

    current = player_df_5on5[player_df_5on5['season'] == selected_season].copy()
    prior = player_df_5on5[player_df_5on5['season'] == prior_season].copy()

    if pos_val:
        current = current[current['pos_group'] == pos_val]
        prior = prior[prior['pos_group'] == pos_val]

    common_players = set(current['playerId'].unique()) & set(prior['playerId'].unique())

    if not common_players:
        st.warning("No players found in both seasons.")
        return

    yoy_rows = []
    for pid in common_players:
        cur_row = current[current['playerId'] == pid].iloc[0]
        pri_row = prior[prior['playerId'] == pid].iloc[0]

        pos_group = cur_row['pos_group']
        cur_pcts = compute_player_percentiles(cur_row, selected_season, pos_group)
        pri_pcts = compute_player_percentiles(pri_row, prior_season, pos_group)

        cur_gs_pct = cur_pcts.get('gameScore', 50)
        pri_gs_pct = pri_pcts.get('gameScore', 50)
        gs_delta = cur_gs_pct - pri_gs_pct

        team_changed = cur_row['team'] != pri_row['team']

        yoy_rows.append({
            'playerId': pid,
            'name': cur_row['name'],
            'position': cur_row['position'],
            'pos_group': pos_group,
            'team_current': cur_row['team'],
            'team_prior': pri_row['team'],
            'team_changed': team_changed,
            'gp_current': int(cur_row['games_played']),
            'gp_prior': int(pri_row['games_played']),
            'gs_pct_current': cur_gs_pct,
            'gs_pct_prior': pri_gs_pct,
            'gs_raw_current': float(cur_row['gameScore']),
            'gs_raw_prior': float(pri_row['gameScore']),
            'gs_delta': gs_delta,
            'pcts_current': cur_pcts,
            'pcts_prior': pri_pcts,
            'raw_current': {k: float(cur_row[k]) for k in metric_keys if k in cur_row.index},
            'raw_prior': {k: float(pri_row[k]) for k in metric_keys if k in pri_row.index},
        })

    yoy_df = pd.DataFrame(yoy_rows).sort_values('gs_delta', ascending=False)

    st.markdown("---")

    top_n = 10
    risers = yoy_df.head(top_n)
    fallers = yoy_df.tail(top_n).iloc[::-1]

    col_rise, col_fall = st.columns(2)
    with col_rise:
        st.subheader(f"Top {top_n} Risers")
        for _, row in risers.iterrows():
            team_note = f" *(from {row['team_prior']})*" if row['team_changed'] else ""
            delta_str = f"+{row['gs_delta']:.1f}"
            st.markdown(
                f"**{row['name']}** — {row['team_current']}{team_note} "
                f"<span style='color:#2A9D8F; font-weight:bold;'>{delta_str}</span> "
                f"<span style='color:gray;'>({row['gs_raw_prior']:.2f} → {row['gs_raw_current']:.2f})</span>",
                unsafe_allow_html=True
            )
    with col_fall:
        st.subheader(f"Top {top_n} Fallers")
        for _, row in fallers.iterrows():
            team_note = f" *(from {row['team_prior']})*" if row['team_changed'] else ""
            delta_str = f"{row['gs_delta']:.1f}"
            st.markdown(
                f"**{row['name']}** — {row['team_current']}{team_note} "
                f"<span style='color:#E63946; font-weight:bold;'>{delta_str}</span> "
                f"<span style='color:gray;'>({row['gs_raw_prior']:.2f} → {row['gs_raw_current']:.2f})</span>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.subheader("League-Wide YoY Performance")
    st.caption(f"Click any column header to sort. Metric columns show percentile (raw value) for each season.")

    table_rows = []
    sort_keys = []
    for _, row in yoy_df.iterrows():
        team_str = row['team_current']
        if row['team_changed']:
            team_str += f" (from {row['team_prior']})"
        table_row = {
            'Player': row['name'],
            'Pos': row['position'],
            'Team': team_str,
            'GP': f"{row['gp_prior']} → {row['gp_current']}",
            'Game Score': f"{row['gs_raw_prior']:.2f} → {row['gs_raw_current']:.2f}",
            'GS Pctl': f"{row['gs_pct_prior']:.0f} → {row['gs_pct_current']:.0f}",
            'GS YoY Δ': round(row['gs_delta'], 1),
        }
        sk = {
            'Game Score': row['gs_raw_current'],
            'GS Pctl': row['gs_pct_current'],
            'GS YoY Δ': row['gs_delta'],
        }
        for k in metric_keys:
            name = ALL_DISPLAY_METRICS[k]['name']
            pri_pct = int(round(row['pcts_prior'].get(k, 50)))
            cur_pct = int(round(row['pcts_current'].get(k, 50)))
            pri_raw = row['raw_prior'].get(k, 0)
            cur_raw = row['raw_current'].get(k, 0)
            table_row[name] = f"{pri_pct}% ({format_raw(k, pri_raw)}) → {cur_pct}% ({format_raw(k, cur_raw)})"
            sk[name] = cur_pct
        table_rows.append(table_row)
        sort_keys.append(sk)

    table_df = pd.DataFrame(table_rows)
    sort_df = pd.DataFrame(sort_keys)

    sortable_cols = ['GS YoY Δ', 'Game Score', 'GS Pctl'] + [ALL_DISPLAY_METRICS[k]['name'] for k in metric_keys if k != 'gameScore']
    TEAM_FULL_NAMES = {
        'ANA': 'Anaheim Ducks', 'ARI': 'Arizona Coyotes', 'BOS': 'Boston Bruins',
        'BUF': 'Buffalo Sabres', 'CAR': 'Carolina Hurricanes', 'CBJ': 'Columbus Blue Jackets',
        'CGY': 'Calgary Flames', 'CHI': 'Chicago Blackhawks', 'COL': 'Colorado Avalanche',
        'DAL': 'Dallas Stars', 'DET': 'Detroit Red Wings', 'EDM': 'Edmonton Oilers',
        'FLA': 'Florida Panthers', 'LAK': 'Los Angeles Kings', 'MIN': 'Minnesota Wild',
        'MTL': 'Montreal Canadiens', 'NJD': 'New Jersey Devils', 'NSH': 'Nashville Predators',
        'NYI': 'New York Islanders', 'NYR': 'New York Rangers', 'OTT': 'Ottawa Senators',
        'PHI': 'Philadelphia Flyers', 'PIT': 'Pittsburgh Penguins', 'SEA': 'Seattle Kraken',
        'SJS': 'San Jose Sharks', 'STL': 'St. Louis Blues', 'TBL': 'Tampa Bay Lightning',
        'TOR': 'Toronto Maple Leafs', 'UTA': 'Utah Hockey Club', 'VAN': 'Vancouver Canucks',
        'VGK': 'Vegas Golden Knights', 'WPG': 'Winnipeg Jets', 'WSH': 'Washington Capitals',
    }
    abbrevs = sorted(yoy_df['team_current'].unique().tolist())
    team_options = ['All'] + [TEAM_FULL_NAMES.get(a, a) for a in abbrevs]
    abbrev_lookup = {TEAM_FULL_NAMES.get(a, a): a for a in abbrevs}

    col_sort, col_dir, col_team = st.columns([3, 1, 2])
    with col_sort:
        sort_col = st.selectbox("Sort by", sortable_cols, index=0, key='yoy_sort_col')
    with col_dir:
        sort_dir = st.selectbox("Order", ["Descending", "Ascending"], key='yoy_sort_dir')
    with col_team:
        team_filter = st.selectbox("Team", team_options, index=0, key='yoy_team_filter')

    if team_filter != 'All':
        abbrev = abbrev_lookup[team_filter]
        mask = table_df['Team'].str.startswith(abbrev)
        table_df = table_df[mask]
        sort_df = sort_df[mask]

    ascending = sort_dir == "Ascending"
    sort_order = sort_df[sort_col].sort_values(ascending=ascending).index
    table_df = table_df.loc[sort_order].reset_index(drop=True)
    table_df.insert(0, '#', range(1, len(table_df) + 1))

    st.caption("Use the player selector below to deep dive.")
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        height=min(len(table_df) * 38 + 40, 800),
        column_config={
            '#': st.column_config.NumberColumn('#', width='small'),
        },
    )

    st.markdown("---")
    st.subheader("Player Deep Dive")

    all_players_sorted = yoy_df.sort_values('name')
    player_names = all_players_sorted['name'].tolist()

    if 'yoy_player_select' not in st.session_state:
        default_name = 'Warren Foegele' if 'Warren Foegele' in player_names else player_names[0]
        st.session_state.yoy_player_select = default_name

    selected_player = st.selectbox(
        "Search or select a player",
        player_names,
        key='yoy_player_select'
    )

    p = yoy_df[yoy_df['name'] == selected_player].iloc[0]

    team_label_cur = p['team_current']
    team_label_pri = p['team_prior']
    team_note = ""
    if p['team_changed']:
        team_note = f"  (*Changed teams: {team_label_pri} → {team_label_cur}*)"

    delta_color = "#2A9D8F" if p['gs_delta'] >= 0 else "#E63946"
    delta_sign = "+" if p['gs_delta'] >= 0 else ""
    arrow = "▲" if p['gs_delta'] >= 0 else "▼"

    team_change_html = ""
    if p['team_changed']:
        team_change_html = (
            f"<div style='margin-top:12px; padding:8px 12px; background:rgba(69,123,157,0.15); "
            f"border-radius:6px; font-size:0.85em;'>"
            f"📍 {team_label_pri} ({prior_season}) → {team_label_cur} ({selected_season})</div>"
        )

    st.markdown(f"""
    <div style="display:flex; gap:16px; margin:8px 0 12px 0;">
        <div style="flex:1; padding:16px 20px; background:rgba(255,255,255,0.05); border-radius:10px; border-left:4px solid #457B9D;">
            <div style="color:gray; font-size:0.75em; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;">Game Score</div>
            <div style="font-size:1.6em; font-weight:bold;">{p['gs_raw_prior']:.2f} <span style="color:gray; font-size:0.6em;">→</span> {p['gs_raw_current']:.2f}</div>
        </div>
        <div style="flex:1; padding:16px 20px; background:rgba(255,255,255,0.05); border-radius:10px; border-left:4px solid #457B9D;">
            <div style="color:gray; font-size:0.75em; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;">Percentile (vs. All Skaters)</div>
            <div style="font-size:1.6em; font-weight:bold;">{p['gs_pct_prior']:.0f}th <span style="color:gray; font-size:0.6em;">→</span> {p['gs_pct_current']:.0f}th</div>
        </div>
        <div style="flex:0.7; padding:16px 20px; background:rgba(255,255,255,0.05); border-radius:10px; border-left:4px solid {delta_color};">
            <div style="color:gray; font-size:0.75em; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;">GS YoY Δ</div>
            <div style="font-size:1.6em; font-weight:bold; color:{delta_color};">{arrow} {delta_sign}{p['gs_delta']:.1f}</div>
        </div>
    </div>{team_change_html}
    """, unsafe_allow_html=True)

    pid = p['playerId']
    all_cur = player_df_all[(player_df_all['playerId'] == pid) & (player_df_all['season'] == selected_season)]
    all_pri = player_df_all[(player_df_all['playerId'] == pid) & (player_df_all['season'] == prior_season)]

    def extract_stats(row):
        gp = int(row.get('games_played', 0))
        g = int(row.get('I_F_goals', 0))
        pts = int(row.get('I_F_points', 0))
        a = pts - g
        hits = int(row.get('I_F_hits', 0))
        blk = int(row.get('shotsBlockedByPlayer', 0))
        icetime = float(row.get('icetime', 0))
        if gp > 0:
            avg_min = icetime / 60 / gp
            mm = int(avg_min)
            ss = int(round((avg_min - mm) * 60))
            toi_gp = f"{mm}:{ss:02d}"
        else:
            toi_gp = "—"
        pts_gp = f"{pts / gp:.2f}" if gp > 0 else "—"
        return {'GP': gp, 'G': g, 'A': a, 'PTS': pts, 'PTS/GP': pts_gp, 'HIT': hits, 'BLK': blk, 'TOI/GP': toi_gp}

    stat_rows = []
    if not all_pri.empty:
        s = extract_stats(all_pri.iloc[0])
        s['Season'] = f"{prior_season} ({team_label_pri})"
        stat_rows.append(s)
    if not all_cur.empty:
        s = extract_stats(all_cur.iloc[0])
        s['Season'] = f"{selected_season} ({team_label_cur})"
        stat_rows.append(s)

    if stat_rows:
        cols = ['GP', 'G', 'A', 'PTS', 'PTS/GP', 'HIT', 'BLK', 'TOI/GP']
        header = "".join(f"<th style='padding:6px 14px; text-align:center; color:gray; font-weight:600; font-size:0.8em; letter-spacing:0.05em;'>{c}</th>" for c in cols)
        rows_html = ""
        for s in stat_rows:
            cells = "".join(f"<td style='padding:8px 14px; text-align:center; font-size:1.1em; font-weight:bold;'>{s[c]}</td>" for c in cols)
            rows_html += f"<tr><td style='padding:8px 14px; font-weight:600; white-space:nowrap;'>{s['Season']}</td>{cells}</tr>"
        st.markdown(
            f"<table style='border-collapse:collapse; margin:8px 0;'>"
            f"<thead><tr><th style='padding:6px 14px; text-align:left; color:gray; font-weight:600; font-size:0.8em;'>Season</th>{header}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    st.markdown("**Performance Radar**")
    st.caption(
        f"*{selected_player} — {prior_season} vs {selected_season} · "
        f"Position: {p['position']} · Game Score vs. all skaters · Other metrics vs. {'forwards' if p['pos_group'] == 'F' else 'defensemen'}*"
    )

    display_names = [ALL_DISPLAY_METRICS[k]['name'] for k in metric_keys]
    pri_values = [p['pcts_prior'].get(k, 50) for k in metric_keys]
    cur_values = [p['pcts_current'].get(k, 50) for k in metric_keys]

    display_names_closed = display_names + [display_names[0]]
    pri_closed = pri_values + [pri_values[0]]
    cur_closed = cur_values + [cur_values[0]]

    pri_labels = []
    cur_labels = []
    for k in metric_keys:
        pri_pct = p['pcts_prior'].get(k, 50)
        cur_pct = p['pcts_current'].get(k, 50)
        pri_raw = p['raw_prior'].get(k, 0)
        cur_raw = p['raw_current'].get(k, 0)
        pri_labels.append(f"{pri_pct:.0f}% ({format_raw(k, pri_raw)})")
        cur_labels.append(f"{cur_pct:.0f}% ({format_raw(k, cur_raw)})")

    pri_labels_closed = pri_labels + [pri_labels[0]]
    cur_labels_closed = cur_labels + [cur_labels[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=pri_closed,
        theta=display_names_closed,
        fill='toself',
        name=f"{selected_player} ({prior_season})",
        line=dict(width=3, color='#457B9D'),
        fillcolor='#457B9D',
        opacity=0.4,
        text=pri_labels_closed,
        hovertemplate='%{text}<extra>' + f'{prior_season}' + '</extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=pri_values,
        theta=display_names,
        mode='text',
        text=pri_labels,
        textposition='bottom center',
        textfont=dict(size=14, color='#457B9D'),
        showlegend=False,
        hoverinfo='skip',
    ))

    fig.add_trace(go.Scatterpolar(
        r=cur_closed,
        theta=display_names_closed,
        fill='toself',
        name=f"{selected_player} ({selected_season})",
        line=dict(width=3, color='#E63946'),
        fillcolor='#E63946',
        opacity=0.4,
        text=cur_labels_closed,
        hovertemplate='%{text}<extra>' + f'{selected_season}' + '</extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=cur_values,
        theta=display_names,
        mode='text',
        text=cur_labels,
        textposition='top center',
        textfont=dict(size=14, color='#E63946'),
        showlegend=False,
        hoverinfo='skip',
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
            yanchor='top',
            y=-0.05,
            xanchor='center',
            x=0.5,
            font=dict(size=15)
        ),
        height=700,
        margin=dict(t=80, b=80, l=100, r=100),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        dragmode=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("How is the YoY ranking calculated?"):
        st.markdown("""
The **YoY ranking** uses **Game Score** — a single-number composite game impact rating
already built into the MoneyPuck data. It captures goals, assists, shot generation,
defensive contributions, and penalty differential in one metric.

**How it works:**
1. Each player's Game Score is converted to a **percentile vs. all skaters** in that season
   (not split by position — forwards and defensemen are ranked together).
2. The **GS YoY Δ** is simply the change in that percentile from the prior season to the current season.
3. A positive Δ means the player improved relative to the league; negative means regression.

**Interpretation:** A player at the 85th percentile with a GS YoY Δ of +20 went from roughly
the 65th percentile to the 85th — a significant breakout. The radar chart and table still
show all 10 detailed metrics for deeper context.
        """)


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
            player_a_options = [f"{row['name']} ({row['position']})" 
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
            player_b_options = [f"{row['name']} ({row['position']})" 
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
