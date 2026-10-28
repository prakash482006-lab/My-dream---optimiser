import os
import streamlit as st
import pandas as pd
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, PULP_CBC_CMD

st.set_page_config(page_title="Dream11 Auto-Team", page_icon="ðŸ", layout="centered")

st.title("ðŸ Dream11 Auto-Team Generator")
st.write("Generate the mathematically optimal team within the 100-credit budget.")

# Default Player Data Setup
default_players = [
    {"Name": "Virat Kohli", "Role": "BAT", "Credits": 10.5, "Form_Points": 85, "Team": "IND"},
    {"Name": "Rohit Sharma", "Role": "BAT", "Credits": 10.0, "Form_Points": 78, "Team": "IND"},
    {"Name": "Jasprit Bumrah", "Role": "BOWL", "Credits": 9.5, "Form_Points": 92, "Team": "IND"},
    {"Name": "Hardik Pandya", "Role": "AR", "Credits": 9.0, "Form_Points": 65, "Team": "IND"},
    {"Name": "Rishabh Pant", "Role": "WK", "Credits": 8.5, "Form_Points": 70, "Team": "IND"},
    {"Name": "Travis Head", "Role": "BAT", "Credits": 9.5, "Form_Points": 88, "Team": "AUS"},
    {"Name": "Glenn Maxwell", "Role": "AR", "Credits": 9.0, "Form_Points": 55, "Team": "AUS"},
    {"Name": "Pat Cummins", "Role": "BOWL", "Credits": 9.0, "Form_Points": 74, "Team": "AUS"},
    {"Name": "Mitchell Starc", "Role": "BOWL", "Credits": 8.5, "Form_Points": 60, "Team": "AUS"},
    {"Name": "Adam Zampa", "Role": "BOWL", "Credits": 8.5, "Form_Points": 80, "Team": "AUS"},
    {"Name": "Josh Inglis", "Role": "WK", "Credits": 8.0, "Form_Points": 50, "Team": "AUS"},
    {"Name": "Yashasvi Jaiswal", "Role": "BAT", "Credits": 8.5, "Form_Points": 72, "Team": "IND"},
    {"Name": "Ravindra Jadeja", "Role": "AR", "Credits": 9.0, "Form_Points": 62, "Team": "IND"},
    {"Name": "Kuldeep Yadav", "Role": "BOWL", "Credits": 8.5, "Form_Points": 68, "Team": "IND"},
    {"Name": "Mohammed Siraj", "Role": "BOWL", "Credits": 8.0, "Form_Points": 48, "Team": "IND"},
    {"Name": "Marcus Stoinis", "Role": "AR", "Credits": 8.0, "Form_Points": 45, "Team": "AUS"},
]

# State Management for Dataframe
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(default_players)

st.subheader("1. Match Player Pool & Stats")
st.write("Edit credits or Form Points directly in the table below:")

# Editable Data Grid
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
st.session_state.df = edited_df

# Add New Player Section
with st.expander("âž• Add a New Player Quickly"):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: new_name = st.text_input("Name", "Player X")
    with col2: new_role = st.selectbox("Role", ["WK", "BAT", "AR", "BOWL"])
    with col3: new_credits = st.number_input("Credits", 1.0, 15.0, 8.5, 0.5)
    with col4: new_pts = st.number_input("Form Points", 0, 200, 50, 5)
    with col5: new_team = st.text_input("Team Code", "IND")
    
    if st.button("Add to Pool"):
        new_row = pd.DataFrame([{"Name": new_name, "Role": new_role, "Credits": new_credits, "Form_Points": new_pts, "Team": new_team}])
        st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
        st.rerun()

st.subheader("2. Run Optimizer")
if st.button("âš¡ Generate Best Dream11 Lineup", type="primary"):
    data = st.session_state.df.to_dict('records')
    
    # Mathematical Optimization using PuLP
    prob = LpProblem("Dream11_Optimizer", LpMaximize)
    player_vars = LpVariable.dicts("P", [p["Name"] for p in data], cat="Binary")
    
    # Objective: Maximize expected points
    prob += lpSum([p["Form_Points"] * player_vars[p["Name"]] for p in data])
    
    # Core Constraints
    prob += lpSum([player_vars[p["Name"]] for p in data]) == 11
    prob += lpSum([p["Credits"] * player_vars[p["Name"]] for p in data]) <= 100.0
    
    # Position Constraints (Dream11 standard rules: 1-8 players per category)
    for role in ["WK", "BAT", "AR", "BOWL"]:
        prob += lpSum([player_vars[p["Name"]] for p in data if p["Role"] == role]) >= 1
        prob += lpSum([player_vars[p["Name"]] for p in data if p["Role"] == role]) <= 8
        
    # Team Cap Constraint (Max 10 players from a single team under new rules)
    teams = set([p["Team"] for p in data])
    for team in teams:
        prob += lpSum([player_vars[p["Name"]] for p in data if p["Team"] == team]) <= 10

    # Solve the problem
    status = prob.solve(PULP_CBC_CMD(msg=False))
    
    if status == 1: # Optimal solution found
        selected_players = [p for p in data if player_vars[p["Name"]].varValue == 1]
        result_df = pd.DataFrame(selected_players)
        
        # Sort by Form Points to pick Captain and Vice-Captain
        result_df = result_df.sort_values(by="Form_Points", ascending=False).reset_index(drop=True)
        
        st.success("ðŸŽ‰ Best 11-Player Team Generated Successfully!")
        
        # Display Key Summary Metrics
        total_credits = result_df["Credits"].sum()
        total_points = result_df["Form_Points"].sum()
        
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric("Total Budget Used", f"{total_credits} / 100 Credits")
        metric_col2.metric("Total Projected Form Points", f"{total_points} Pts")
        
        # Highlight C and VC
        st.subheader("ðŸ’¡ Recommended Captain & Vice-Captain")
        st.info(f"ðŸ‘‘ **Captain (2x Points):** {result_df.loc[0, 'Name']} ({result_df.loc[0, 'Role']})

ðŸƒ **Vice-Captain (1.5x Points):** {result_df.loc[1, 'Name']} ({result_df.loc[1, 'Role']})")
        
        st.subheader("ðŸ“‹ Selected Lineup")
        st.dataframe(result_df[["Name", "Role", "Team", "Credits", "Form_Points"]], use_container_width=True)
    else:
        st.error("Could not find a valid team setup. Check your budget or criteria adjustments.")
