import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Dream11 Dual-Mode Optimizer", layout="centered")

st.title("🏏 Dream11 Multi-Team Builder")
st.write("Add your 22-24 players manually. Choose either the Player Lock mode or Target Sliders mode to build up to 40 unique team variations.")

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
    
    submit = st.form_submit_button("Add Player")
    if submit and p_name:
        st.session_state.player_data.append({
            "Name": p_name, "Role": p_role, "Credits": p_credits, "Lock_In_All_Teams": False
        })
        st.success(f"Added {p_name} to the pool!")

# Interactive Grid
st.subheader("📋 Your Custom Player Pool")

if len(st.session_state.player_data) == 0:
    st.info("Your pool is empty. Use the form above to add players.")
    df = pd.DataFrame(columns=["Name", "Role", "Credits", "Lock_In_All_Teams"])
else:
    df = pd.DataFrame(st.session_state.player_data)
    df = df[["Name", "Role", "Credits", "Lock_In_All_Teams"]]

st.write("Edit names, roles, or credits directly below. The 'Lock' checkbox will only apply if Lock Mode is turned on.")
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

if not edited_df.equals(df):
    st.session_state.player_data = edited_df.to_dict('records')

# Strategy Mode Selector
st.subheader("🛠️ Choose Strategy Mode")
optimizer_mode = st.radio(
    "Select which strategy rule to enforce for this generation:",
    ["🔒 Lock Mode (Force specific players into all teams)", "🎛️ Sliders Mode (Enforce exact position counts)"],
    index=0
)

# Render Controls Conditionally based on Toggle
target_wk, target_bat, target_ar, target_bowl = 1, 3, 3, 4 # Default baselines if mode is off

if "🔒 Lock Mode" in optimizer_mode:
    st.info("💡 **Active Strategy:** The engine will force your selected 'Lock' players into all lineups and automatically balance the remaining slots using Dream11 standard rules.")
else:
    st.info("💡 **Active Strategy:** The engine will ignore all checked lock boxes and build lineups matching your exact slider combinations below.")
    
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

    total_requested_slots = target_wk + target_bat + target_ar + target_bowl
    st.info(f"Total slots chosen per team: **{total_requested_slots} / 11**")

# Number of Teams Selector
st.subheader("🤖 Generation Settings")
num_teams_to_gen = st.number_input("How many unique teams do you want to generate?", min_value=1, max_value=40, value=10, step=1)

# Optimization Run Button
if st.button("🚀 Generate Teams", type="primary"):
    cleaned_df = edited_df.dropna(subset=["Name"]).copy()
    cleaned_df = cleaned_df[cleaned_df["Name"].astype(str).str.strip() != ""]
    cleaned_df = cleaned_df.reset_index(drop=True)
    
    total_locked = int(cleaned_df["Lock_In_All_Teams"].sum())
    
    # Run validation checks depending on active strategy mode
    mode_validated = True
    if "🎛️ Sliders Mode" in optimizer_mode and total_requested_slots != 11:
        st.error(f"Your sliders add up to {total_requested_slots} players. They must add up to exactly 11 players.")
        mode_validated = False
    elif "🔒 Lock Mode" in optimizer_mode and total_locked > 11:
        st.error(f"You have checked {total_locked} players. You cannot lock more than 11 players into a team.")
        mode_validated = False
    elif len(cleaned_df) < 11:
        st.error(f"You need to enter at least 11 players in your grid to generate a squad.")
        mode_validated = False
        
    if mode_validated:
        generated_lineups = []
        prob = LpProblem("Dream11_DualMode_Maximizer", LpMaximize)
        
        # FIXED: Corrected spelling to native `LpVariable.dicts` with precise parameters.
        # String indices ensure it won't conflict with library types.
        player_indices_str = [str(i) for i in cleaned_df.index]
        player_vars = LpVariable.dicts("choice", player_indices_str, cat="Binary")
            
        prob += lpSum([cleaned_df.loc[i, "Credits"] * player_vars[str(i)] for i in cleaned_df.index])
        
        # Base rules applied to both modes
        prob += lpSum([player_vars[str(i)] for i in cleaned_df.index]) == 11
        prob += lpSum([cleaned_df.loc[i, "Credits"] * player_vars[str(i)] for i in cleaned_df.index]) <= 100.0
        
        # Mode 1: Apply strict user value slider structures
        if "🎛️ Sliders Mode" in optimizer_mode:
            prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "WK"]) == target_wk
            prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "BAT"]) == target_bat
            prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "AR"]) == target_ar
            prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == "BOWL"]) == target_bowl
        
        # Mode 2: Apply Lock Constraints & standard Dream11 bounds (1 to 8 players per role)
        else:
            for role in ["WK", "BAT", "AR", "BOWL"]:
                prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == role]) >= 1
                prob += lpSum([player_vars[str(i)] for i in cleaned_df.index if cleaned_df.loc[i, "Role"] == role]) <= 8
                
            for i in cleaned_df.index:
                if cleaned_df.loc[i, "Lock_In_All_Teams"] == True:
                    prob += player_vars[str(i)] == 1
                    
        # Multi-team execution loop
        for t_idx in range(1, num_teams_to_gen + 1):
            status = prob.solve(PULP_CBC_CMD(msg=False))
            
            if LpStatus[status] == "Optimal":
                selected_indices = [i for i in cleaned_df.index if player_vars[str(i)].varValue == 1]
                result_df = cleaned_df.loc[selected_indices].copy()
                
                display_df = result_df.drop(columns=["Lock_In_All_Teams"])
                display_df = display_df.reset_index(drop=True)
                
                generated_lineups.append((t_idx, display_df))
                prob += lpSum([player_vars[str(i)] for i in selected_indices]) <= 9
            else:
                if t_idx == 1:
                    st.error("No valid combination matches your selected strategy mode criteria. Change your setup options or check player credits.")
                else:
                    st.warning(f"Could only generate {len(generated_lineups)} unique teams before running out of valid combinations.")
                break
                
        if generated_lineups:
            st.success(f"Successfully generated {len(generated_lineups)} unique team lineups!")
            for t_num, team_df in generated_lineups:
                with st.expander(f"📋 TEAM {t_num} (Total Credits Used: {team_df['Credits'].sum()} / 100)"):
                    st.dataframe(team_df, use_container_width=True)
                    if len(team_df) >= 2:
                        st.info(f"👑 **Captain:** {team_df.loc[0, 'Name']} | ✨ **Vice-Captain:** {team_df.loc[1, 'Name']}")
