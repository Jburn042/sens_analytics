# Trade Simulator Rebuild — Proper Standings Model Integration

## Status: Planned (not yet implemented)

## Problem Statement

The trade simulator currently **bypasses the standings model**. Instead of computing how a player swap changes team metrics and re-predicting rank from those metrics, it uses a gameScore-based coefficient (`GS_TOTAL_COEFF = -0.055`) to directly adjust the predicted score. The radar chart metric changes and the rank prediction are driven by two disconnected mechanisms.

### Current (hacky) flow

```
Player swap → gameScore delta → magic coefficient → predicted score adjustment → rank
                              ↘ GS/60 slopes → cosmetic metric changes (radar only)
```

### Correct flow

```
Player swap → recalculate full roster metrics → feed into standings model → rank
```

The standings model (RandomForest) is already well-calibrated. The trade simulator should use it, not work around it.

---

## The Core Challenge

The 8 team metrics the standings model uses:

| Metric | Type | Affected by skater trade? |
|--------|------|--------------------------|
| `net_flurry_xgoals` | On-ice xGoals differential | Yes |
| `net_score_adjusted_shots` | On-ice shot attempt differential | Yes |
| `corsipercentage` | On-ice Corsi% | Yes |
| `net_high_danger_shots` | On-ice HD shot differential | Yes |
| `net_high_danger_xgoals` | On-ice HD xGoals differential | Yes |
| `shooting_percentage` | Individual shooting % | Yes |
| `save_percentage` | Goalie metric | No |
| `goals_saved_above_expected` | Goalie metric | No |

Six metrics are **on-ice team stats recorded while a specific player is on the ice**. They reflect all 5 skaters, not just the individual. Previous attempts to isolate individual marginal contributions failed because a good player on a strong team (e.g., Pinto on OTT) appeared to have poor marginal contribution — the team average was already high.

---

## What Already Exists in `roster_simulation.py`

The building blocks are already written but were abandoned:

- **`_calculate_raw_roster_metrics(roster)`** — computes ice-time-weighted averages of on-ice stats for a roster. This IS the "roster → team metrics" function.
- **`_calculate_scaling_factors()`** — calibrates the gap between roster-calculated metrics and actual team-level data (the model's training data).
- **`calculate_team_metrics_from_roster(roster, goalie_metrics)`** — applies scaling factors to produce model-compatible team metrics.

---

## Proposed Approach

### Key Insight

Don't try to isolate individual player marginal contributions. Instead, **swap the player in the roster and recalculate the full team metrics from scratch**. The existing `_calculate_raw_roster_metrics` already does this correctly for a full roster.

### Step 1 — Validate the roster-to-metric pipeline

Before changing trade logic, verify that `_calculate_raw_roster_metrics` + scaling factors accurately reproduce actual team metrics for all 32 teams. If the pipeline is accurate at the team level, it should be trustworthy for "what-if" roster changes too.

### Step 2 — Implement swap-and-recalculate

For team A (loses player_out, gains player_in):
1. Take team A's full current-season roster
2. Remove player_out's row
3. Add player_in's row (with their stats from their current/selected season)
4. Run `calculate_team_metrics_from_roster()` on the modified roster
5. Feed the result into the existing standings model to get the new predicted rank

No marginal contribution math. No gameScore coefficients. Just: new roster → new metrics → model predicts rank.

### Step 3 — Address the contamination concern

Player_in's on-ice stats were recorded with their *old* team's context. When they move to a new team, those stats won't perfectly transfer. However:
- This is inherent to any model using available data — we can only project from what we have
- Full-roster recalculation naturally dilutes any single player's on-ice stats across the team average (one player is ~3-7% of total ice time)
- This is the same limitation real NHL analytics teams face and is the accepted approach

### Step 4 — Remove the gameScore bypass

Once the roster-recalculation approach produces sensible results, remove:
- `GS_TOTAL_COEFF` and the total-GS scoring adjustment
- `GS_METRIC_SLOPES` and the cosmetic metric changes
- The `score_adjustment` / `baseline_metrics` parameters from `predict_team_rank_with_context`
- The `_compute_team_gs60` method

---

## Test Scenarios

These should be validated after implementation:

| Trade | Expected: Team A | Expected: Team B |
|-------|-----------------|-----------------|
| McDavid ↔ Eller | EDM gets much worse | OTT gets much better |
| Pinto ↔ Killorn | OTT gets slightly worse | ANA gets slightly better |
| McDavid ↔ MacKinnon | EDM ~unchanged | COL ~unchanged |
| McDavid ↔ Bedard | EDM gets worse | CHI gets much better |

McDavid should represent the extreme of how much a single player can move a team.

---

## Key Files

- `roster_simulation.py` — all trade logic lives here
- `standings_model.py` — the RandomForest model and training pipeline
- `app.py` — UI layer that calls `simulate_trade()` and displays results (should need minimal changes)

---

## Open Questions

1. How accurate is the existing `_calculate_raw_roster_metrics` + scaling pipeline? If it poorly reproduces actual team metrics, the whole approach needs a different calibration strategy.
2. Should we normalize player_in's on-ice stats to the new team's context somehow, or accept the raw transfer as-is?
3. The current approach uses `player_data_all` (5v5 data). Verify that the on-ice columns used in `_calculate_raw_roster_metrics` align with the team metrics the model was trained on.
