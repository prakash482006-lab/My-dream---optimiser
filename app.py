import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Dream11 Optimizer", layout="centered")

st.title("🏏 Dream11 Team Optimizer")
st.write("Enter your player pool, select metrics, and generate the mathematically optimal 11-player team lineup instantly.")

# Initial Sample Dataset
if 'player_data' not in st.session_state:
    st.session_state.player_data = [
        {"Name": "Player 1", "Role": "WK", "Credits": 9.0, "Proj_Points": 55, "Team": "IND"},
        {"Name": "Player 2", "Role": "BAT", "Credits": 10.5, "Proj_Points": 70, "Team": "IND"},
        {"Name": "Player 3", "Role": "BAT", "Credits": 9.5, "Proj_Points": 62, "Team": "AUS"},
        {"Name": "Player 4", "Role": "AR", "Credits": 9.0, "Proj_Points": 58, "Team": "IND"},
        {"Name": "Player 5", "Role": "AR", "Credits": 8.5, "Proj_Points": 50, "Team": "AUS"},
        {"Name": "Player 6", "Role": "BOWL", "Credits": 8.5, "Proj_Points": 48, "Team": "AUS"},
        {"Name": "Player 7", "Role": "BOWL", "Credits": 8.0, "Proj_Points": 45, "Team": "IND"},
        {"Name": "Player 8", "Role": "WK", "Credits": 8.5, "Proj_Points": 40, "Team": "AUS"},
        {"Name": "Player 9", "Role": "BAT", "Credits": 8.5, "Proj_Points": 42, "Team": "IND"},
        {"Name": "Player 10", "Role": "BOWL", "Credits": 7.5, "Proj_Points": 38, "Team": "IND"},
        {"Name": "Player 11", "Role": "BOWL", "Credits": 7.0, "Proj_Points": 35, "Team": "AUS"},
        {"Name": "Player 12", "Role": "AR", "Credits": 9.0, "Proj_Points": 52, "Team": "AUS"},
    ]

# Form to add a new player manually
st.subheader("➕ Add New Player")
with st.form("add_player_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        p_name = st.text_input("Player Name")
        p_role = st.selectbox("Role", ["WK", "BAT", "AR", "BOWL"])
    with col2:
        p_credits = st.number_input("Credits", min_value=1.0, max_value=20.0, value=9.0, step=0.5)
        p_points = st.number_input("Projected Points", min_value=0, max_value=200, value=40)
    p_team = st.text_input("Team Code (e.g., IND, AUS)", value="IND").upper()
    
    submit = st.form_submit_with_categorical_features = st.form_submit_button("Add Player to Roster")
    if submit and p_name:
        st.session_state.player_data.append({
            "Name": p_name, "Role": p_role, "Credits": p_credits, "Proj_Points": p_points, "Team": p_team
        })
        st.success(f"Added {p_name} successfully!")

# Editable Interactive Grid
st.subheader("📋 Current Player Pool")
st.write("Double-tap values below to edit credits or points directly on your phone:")
df = pd.DataFrame(st.session_state.player_data)
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# Optimization Run Button
if st.button("🚀 Generate Optimal Team", type="primary"):
    if len(edited_df) < 11:
        st.error("You must have at least 11 players in the list to build a team.")
    else:
        # Define Optimization Problem
        prob = LpProblem("Dream11_Maximizer", LpMaximize)
        
        # Decision dictionary
        player_names = edited_df["Name"].tolist()
        player_vars = LpVariable.dicts("Select", player_names, cat="Binary")
        
        # Objective function (Maximize points)
        prob += lpSum([edited_df.loc[i, "Proj_Points"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index])
        
        # Rule 1: Exactly 11 players
        prob += lpSum([player_vars[name] for name in player_names]) == 11
        
        # Rule 2: Under 100 Credits budget
        prob += lpSum([edited_df.loc[i, "Credits"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index]) <= 100.0
        
        # Rule 3: Balance constraints (1 to 8 players per position role)
        for role in ["WK", "BAT", "AR", "BOWL"]:
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == role]) >= 1
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == role]) <= 8
            
        # Rule 4: Maximum 10 players from a single real team
        teams = edited_df["Team"].unique()
        for t in teams:
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Team"] == t]) <= 10
            
        # Solve the math model
        status = prob.solve(PULP_CBC_CMD(msg=False))
        
        if LpStatus[status] == "Optimal":
            selected_names = [name for name in player_names if player_vars[name].varValue == 1]
            result_df = edited_df[edited_df["Name"].isin(selected_names)].copy()
            
            # Sort by points to find highest projected performers for captaincy recommendation
            result_df = result_df.sort_values(by="Proj_Points", ascending=False).reset_index(drop=True)
            
            st.subheader("🔥 Your Automated Dream11 Lineup")
            st.dataframe(result_df, use_container_width=True)
            
            # Key statistics display
            total_credits = result_df["Credits"].sum()
            total_points = result_df["Proj_Points"].sum()
            
            st.metric("Total Credits Used", f"{total_credits} / 100")
            st.metric("Total Projected Performance Points", f"{total_points}")
            
            # Smart Recommendations for C and VC based on point distributions
            if len(result_df) >= 2:
                c_name = result_df.loc[0, "Name"]
                c_role = result_df.loc[0, "Role"]
                vc_name = result_df.loc[1, "Name"]
                vc_role = result_df.loc[1, "Role"]
                st.info(f"👑 **Captain (2x Points):** {c_name} ({c_role})")
                st.info(f"✨ **Vice-Captain (1.5x Points):** {vc_name} ({vc_role})")
        else:
            st.error("No valid combination fits within the 100-credit budget. Try editing your player credit values.")
