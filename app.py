import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Dream11 Custom Optimizer", layout="centered")

st.title("🏏 Dream11 Custom Team Builder")
st.write("Add your 22-24 players manually, set your positions, and let the math solver build the perfect 11.")

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

# Validation check to ensure selections add up to 11
total_requested_slots = target_wk + target_bat + target_ar + target_bowl
st.info(f"Total slots chosen: **{total_requested_slots} / 11**")

# Optimization Run Button
if st.button("🚀 Generate Custom Team", type="primary"):
    # Clear out any empty rows or missing values safely
    cleaned_df = edited_df.dropna(subset=["Name"]).copy()
    cleaned_df = cleaned_df[cleaned_df["Name"].astype(str).str.strip() != ""]
    
    # Reset index so we can use clean numeric IDs for the optimization variables
    cleaned_df = cleaned_df.reset_index(drop=True)
    
    if total_requested_slots != 11:
        st.error(f"Your sliders add up to {total_requested_slots} players. They must add up to exactly 11 players before running the generator.")
    elif len(cleaned_df) < 11:
        st.error(f"You need to enter at least 11 players in your grid to generate a squad. Currently you have {len(cleaned_df)} complete rows.")
    else:
        # Define Optimization Problem
        prob = LpProblem("Dream11_Custom_Maximizer", LpMaximize)
        
        # Use row index integers instead of player names to avoid character/space dictionary errors
        player_indices = list(cleaned_df.index)
        player_vars = LpVariable.dicts("Select", player_indices, cat="Binary")
        
        # Objective function (Maximize total points based on input)
        prob += lpSum([cleaned_df.loc[i, "Proj_Points"] * player_vars[i] for i in player_indices])
        
        # Rule 1: Total must equal 11
        prob += lpSum([player_vars[i] for i in player_indices]) == 11
        
        # Rule 2: Budget under 100 Credits
        prob += lpSum([cleaned_df.loc[i, "Credits"] * player_vars[i] for i in player_indices]) <= 100.0
        
        # Rule 3: Dynamic user-defined constraints for each role
        prob += lpSum([player_vars[i] for i in player_indices if cleaned_df.loc[i, "Role"] == "WK"]) == target_wk
        prob += lpSum([player_vars[i] for i in player_indices if cleaned_df.loc[i, "Role"] == "BAT"]) == target_bat
        prob += lpSum([player_vars[i] for i in player_indices if cleaned_df.loc[i, "Role"] == "AR"]) == target_ar
        prob += lpSum([player_vars[i] for i in player_indices if cleaned_df.loc[i, "Role"] == "BOWL"]) == target_bowl
            
        # Rule 4: Maximum 10 players from a single real team
        teams = cleaned_df["Team"].unique()
        for t in teams:
            prob += lpSum([player_vars[i] for i in player_indices if cleaned_df.loc[i, "Team"] == t]) <= 10
            
        # Solve the math model
        status = prob.solve(PULP_CBC_CMD(msg=False))
        
        if LpStatus[status] == "Optimal":
            selected_indices = [i for i in player_indices if player_vars[i].varValue == 1]
            result_df = cleaned_df.loc[selected_indices].copy()
            
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
