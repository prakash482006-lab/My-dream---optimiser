import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Dream11 Custom Optimizer", layout="centered")

st.title("🏏 Dream11 Custom Team Builder")
st.write("Enter your 22-24 players manually, set your exact position preferences, and let the math solver build the perfect 11.")

# Initial Sample Dataset (Clean layout for you to start typing over)
if 'player_data' not in st.session_state:
    st.session_state.player_data = [
        {"Name": "Player 1", "Role": "WK", "Credits": 9.0, "Proj_Points": 50, "Team": "TEAM_A"},
        {"Name": "Player 2", "Role": "BAT", "Credits": 10.5, "Proj_Points": 70, "Team": "TEAM_A"},
        {"Name": "Player 3", "Role": "BAT", "Credits": 9.5, "Proj_Points": 60, "Team": "TEAM_B"},
        {"Name": "Player 4", "Role": "AR", "Credits": 9.0, "Proj_Points": 55, "Team": "TEAM_A"},
        {"Name": "Player 5", "Role": "AR", "Credits": 8.5, "Proj_Points": 48, "Team": "TEAM_B"},
        {"Name": "Player 6", "Role": "BOWL", "Credits": 8.5, "Proj_Points": 45, "Team": "TEAM_B"},
        {"Name": "Player 7", "Role": "BOWL", "Credits": 8.0, "Proj_Points": 40, "Team": "TEAM_A"},
        {"Name": "Player 8", "Role": "WK", "Credits": 8.5, "Proj_Points": 42, "Team": "TEAM_B"},
        {"Name": "Player 9", "Role": "BAT", "Credits": 8.5, "Proj_Points": 40, "Team": "TEAM_A"},
        {"Name": "Player 10", "Role": "BOWL", "Credits": 7.5, "Proj_Points": 38, "Team": "TEAM_A"},
        {"Name": "Player 11", "Role": "BOWL", "Credits": 7.0, "Proj_Points": 35, "Team": "TEAM_B"},
    ]

# Form to add a new player manually
st.subheader("➕ Add New Player")
with st.form("add_player_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Player Name")
        p_role = st.selectbox("Role / Position", ["WK", "BAT", "AR", "BOWL"])
    with col2:
        p_credits = st.number_input("Credits", min_value=1.0, max_value=20.0, value=9.0, step=0.5)
        p_points = st.number_input("Projected Points (Form/Skill)", min_value=0, max_value=200, value=40)
    p_team = st.text_input("Team Name (e.g., IND, AUS, MI, CSK)", value="IND").upper()
    
    submit = st.form_submit_button("Add Player to Pool")
    if submit and p_name:
        st.session_state.player_data.append({
            "Name": p_name, "Role": p_role, "Credits": p_credits, "Proj_Points": p_points, "Team": p_team
        })
        st.success(f"Added {p_name} to the pool!")

# Interactive Grid
st.subheader("📋 Your 24-Player Pool")
st.write("Type your player names, roles, credits, and point values directly into the table below:")
df = pd.DataFrame(st.session_state.player_data)
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# NEW: Position Filter Configuration Controls
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

# Validation check to ensure selections add up to 11
total_requested_slots = target_wk + target_bat + target_ar + target_bowl
st.info(f"Total slots chosen: **{total_requested_slots} / 11**")

# Optimization Run Button
if st.button("🚀 Generate Custom Team", type="primary"):
    if total_requested_slots != 11:
        st.error(f"Your sliders add up to {total_requested_slots} players. They must add up to exactly 11 players before running the generator.")
    elif len(edited_df) < 11:
        st.error("You need to enter at least 11 players in your grid to generate a squad.")
    else:
        # Define Optimization Problem
        prob = LpProblem("Dream11_Custom_Maximizer", LpMaximize)
        
        player_names = edited_df["Name"].tolist()
        player_vars = LpVariable.dicts("Select", player_names, cat="Binary")
        
        # Objective function (Maximize total points based on input)
        prob += lpSum([edited_df.loc[i, "Proj_Points"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index])
        
        # Rule 1: Total must equal 11
        prob += lpSum([player_vars[name] for name in player_names]) == 11
        
        # Rule 2: Budget under 100 Credits
        prob += lpSum([edited_df.loc[i, "Credits"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index]) <= 100.0
        
        # Rule 3: Dynamic user-defined constraints for each role
        prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == "WK"]) == target_wk
        prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == "BAT"]) == target_bat
        prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == "AR"]) == target_ar
        prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == "BOWL"]) == target_bowl
            
        # Rule 4: Maximum 10 players from a single real team
        teams = edited_df["Team"].unique()
        for t in teams:
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Team"] == t]) <= 10
            
        # Solve the math model
        status = prob.solve(PULP_CBC_CMD(msg=False))
        
        if LpStatus[status] == "Optimal":
            selected_names = [name for name in player_names if player_vars[name].varValue == 1]
            result_df = edited_df[edited_df["Name"].isin(selected_names)].copy()
            
            # Sort by highest points to find best candidates for C and VC
            result_df = result_df.sort_values(by="Proj_Points", ascending=False).reset_index(drop=True)
            
            st.subheader("🔥 Your Tailored Dream11 Lineup")
            st.dataframe(result_df, use_container_width=True)
            
            total_credits = result_df["Credits"].sum()
            total_points = result_df["Proj_Points"].sum()
            
            st.metric("Total Credits Used", f"{total_credits} / 100")
            st.metric("Total Projected Points", f"{total_points}")
            
            if len(result_df) >= 2:
                st.success(f"👑 **Captain (2x Points):** {result_df.loc[0, 'Name']} ({result_df.loc[0, 'Role']})")
                st.success(f"✨ **Vice-Captain (1.5x Points):** {result_df.loc[1, 'Name']} ({result_df.loc[1, 'Role']})")
        else:
            st.error("No valid combination of your entered players matches your exact position requirements while staying under the 100-credit budget. Try adjusting the sliders or editing the credit costs in the grid.")
