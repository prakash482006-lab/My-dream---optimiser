import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Dream11 Multi-Team Optimizer", layout="centered")

st.title("🏏 Dream11 Multi-Team Builder")
st.write("Add your 22-24 players manually, set your structure, choose how many teams you want, and generate them instantly.")

# Initialize a completely empty dataset structure
if 'player_data' not in st.session_state:
    st.session_state.player_data = []

# Form to add a new player manually
st.subheader("➕ Add Player to Pool")
with st.form("add_player_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Player Name")
        p_role = st.selectbox("Role / Position", ["WK", "BAT", "AR", "BOWL"])
    with col2:
        p_credits = st.number_input("Credits cost", min_value=1.0, max_value=20.0, value=9.0, step=0.5)
        p_points = st.number_input("Projected Points", min_value=0, max_value=200, value=40)
    p_team = st.text_input("Team Name (e.g., IND, AUS, MI, CSK)", value="IND").upper()
    
    submit = st.form_submit_button("Add Player")
    if submit and p_name:
        st.session_state.player_data.append({
            "Name": p_name, "Role": p_role, "Credits": p_credits, "Proj_Points": p_points, "Team": p_team
        })
        st.success(f"Added {p_name} to the pool!")

# Interactive Grid with Row Deletion Enabled
st.subheader("📋 Your Custom Player Pool")

if len(st.session_state.player_data) == 0:
    st.info("Your pool is empty. Use the form above to add players, or click the '+' button inside the table below to start typing.")
    df = pd.DataFrame(columns=["Name", "Role", "Credits", "Proj_Points", "Team"])
else:
    df = pd.DataFrame(st.session_state.player_data)

edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# Sync table modifications back to session state to prevent loss on reload
if not edited_df.equals(df):
    st.session_state.player_data = edited_df.to_dict('records')

# Position Filter Configuration Controls
st.subheader("⚙️ Set Target Team Composition")
st.write("Adjust these sliders to choose exactly how many players you want from each role in your final 11:")

col_wk, col_bat = st.columns(2)
with col_wk:
    target_wk = st.slider("Wicket-Keepers (WK) wanted:", min_value=1, max_value=8, value=1)
with col_bat:
    target_bat = st.slider("Batsmen (BAT) wanted:", min_value=1, max_value=8, value=3)

col_ar, col_bowl = st.columns(2)
with col_ar:
    target_ar = st.slider("All-Rounders (AR) wanted:", min_value=1, max_value=8, value=3)
with col_bowl:
    target_bowl = st.slider("Bowlers (BOWL) wanted:", min_value=1, max_value=8, value=4)

# NEW: Number of Teams Selector
st.subheader("🤖 Generation Settings")
num_teams_to_gen = st.number_input("How many unique teams do you want to generate?", min_value=1, max_value=40, value=10, step=1)

# Validation check to ensure selections add up to 11
total_requested_slots = target_wk + target_bat + target_ar + target_bowl
st.info(f"Total slots chosen per team: **{total_requested_slots} / 11**")

# Optimization Run Button
if st.button("🚀 Generate Teams", type="primary"):
    # Clear out any empty rows safely
    cleaned_df = edited_df.dropna(subset=["Name"]).copy()
    cleaned_df = cleaned_df[cleaned_df["Name"].astype(str).str.strip() != ""]
    cleaned_df = cleaned_df.reset_index(drop=True)
    
    if total_requested_slots != 11:
        st.error(f"Your sliders add up to {total_requested_slots} players. They must add up to exactly 11 players before running the generator.")
    elif len(cleaned_df) < 11:
        st.error(f"You need to enter at least 11 players in your grid to generate a squad. Currently you have {len(cleaned_df)} rows.")
    else:
        # Array to hold all historically generated teams to enforce diversity
        generated_lineups = []
        
        # Define base Optimization Problem
        prob = LpProblem("Dream11_Multi_Maximizer", LpMaximize)
        
        # SAFE SYNTAX FIX: Define variables using standard list iteration and explicit string naming
        player_vars = [LpVariable(f"PVar_{i}", cat='Binary') for i in cleaned_df.index]
        
        # Objective function (Maximize total points based on input)
        prob += lpSum([cleaned_df.loc[i, "Proj_Points"] * player_vars[i] for i in cleaned_df.index])
        
        # Core Constraints
        prob += lpSum([player_vars[i] for i in cleaned_df.index]) == 11
        prob += lpSum([cleaned_df.loc[i, "Credits"] * player_vars[i] for i in cleaned_df.index]) <= 100.0
        prob += lpSum([player_vars[i] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "WK"]) == target_wk
        prob += lpSum([player_vars[i] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "BAT"]) == target_bat
        prob += lpSum([player_vars[i] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "AR"]) == target_ar
        prob += lpSum([player_vars[i] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "BOWL"]) == target_bowl
            
        teams = cleaned_df["Team"].unique()
        for t in teams:
            prob += lpSum([player_vars[i] for i in cleaned_df.index if cleaned_df.loc[i, "Team"] == t]) <= 10
            
        # Run loop to find multiple unique combinations
        for t_idx in range(1, num_teams_to_gen + 1):
            status = prob.solve(PULP_CBC_CMD(msg=False))
            
            if LpStatus[status] == "Optimal":
                selected_indices = [i for i in cleaned_df.index if player_vars[i].varValue == 1]
                result_df = cleaned_df.loc[selected_indices].copy()
                result_df = result_df.sort_values(by="Proj_Points", ascending=False).reset_index(drop=True)
                
                # Store the team results
                generated_lineups.append((t_idx, result_df))
                
                # Multi-team constraint block: Force next iteration to be different by outlawing this specific overlap combo
                prob += lpSum([player_vars[i] for i in selected_indices]) <= 9
            else:
                if t_idx == 1:
                    st.error("No valid combination fits your constraints. Adjust your sliders or edit player credits.")
                else:
                    st.warning(f"Could only generate {len(generated_lineups)} unique teams with your current player pool data before running out of combinations.")
                break
        
        # Display all generated teams
        if generated_lineups:
            st.success(f"Successfully generated {len(generated_lineups)} unique team lineups!")
            
            for t_num, team_df in generated_lineups:
                with st.expander(f"📋 TEAM {t_num} (Estimated Points: {team_df['Proj_Points'].sum()} | Credits: {team_df['Credits'].sum()})"):
                    st.dataframe(team_df, use_container_width=True)
                    
                    if len(team_df) >= 2:
                        st.info(f"👑 **Captain:** {team_df.loc[0, 'Name']} | ✨ **Vice-Captain:** {team_df.loc[1, 'Name']}")
