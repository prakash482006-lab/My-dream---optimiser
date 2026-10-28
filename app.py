import streamlit as st
import pandas as pd
import requests
from pulp import *

# Paste your CricketData.org API key here
API_KEY = "e474d44a-f65b-470c-b50c-3463c4c3b164"

st.set_page_config(page_title="Dream11 Auto-Optimizer", layout="centered")
st.title("🏏 Dream11 Automatic Lineup Builder")
st.write("Fetch live match squads automatically using the free Cricket API and instantly generate optimal combinations.")

# --- API FETCHING LOGIC ---
@st.cache_data(ttl=300) # Caches data for 5 minutes to stay under free rate limits
def fetch_upcoming_matches():
    url = f"https://cricapi.com{API_KEY}&offset=0"
    try:
        response = requests.get(url).json()
        if response.get("status") == "success":
            matches = response.get("data", [])
            # Filter for upcoming or recently started games
            return {f"{m['name']} ({m['date']})": m['id'] for m in matches if "matchStarted" in m}
        else:
            st.error(f"API Error: {response.get('reason', 'Unknown error')}")
            return {}
    except Exception as e:
        st.error(f"Failed to connect to Cricket API: {e}")
        return {}

@st.cache_data(ttl=300)
def fetch_match_squad(match_id):
    url = f"https://cricapi.com{API_KEY}&id={match_id}"
    try:
        response = requests.get(url).json()
        player_pool = []
        if response.get("status") == "success":
            data = response.get("data", [])
            for team_info in data:
                team_name = team_info.get("teamName", "UNK")[:3].upper() # Take first 3 letters as code
                players = team_info.get("players", [])
                for p in players:
                    # Map standard cricket roles to Dream11 abbreviations
                    role_raw = p.get("role", "Batsman").lower()
                    if "keeper" in role_raw or "wk" in role_raw:
                        role = "WK"
                    elif "allrounder" in role_raw or "all-rounder" in role_raw or "ar" in role_raw:
                        role = "AR"
                    elif "bowler" in role_raw or "bowl" in role_raw:
                        role = "BOWL"
                    else:
                        role = "BAT"
                    
                    # Note: Free APIs don't supply official Dream11 credits/projections.
                    # We assign realistic smart defaults for the optimizer to handle.
                    player_pool.append({
                        "Name": p.get("name"),
                        "Role": role,
                        "Credits": 9.0, # Default starting credit
                        "Proj_Points": 45, # Default starting projected points
                        "Team": team_name
                    })
            return player_pool
        else:
            st.error("Could not fetch squads for this specific match.")
            return []
    except Exception as e:
        st.error(f"Error compiling squad data: {e}")
        return []

# --- STEP 1: SELECT MATCH ---
st.subheader("📡 Fetch Live Match Data")
match_dict = fetch_upcoming_matches()

if match_dict:
    selected_match_name = st.selectbox("Select an upcoming match:", list(match_dict.keys()))
    match_id = match_dict[selected_match_name]
    
    if st.button("📥 Import Squad Automatically", type="secondary"):
        st.session_state.player_data = fetch_match_squad(match_id)
        st.success(f"Successfully loaded {len(st.session_state.player_data)} players!")
else:
    st.info("No upcoming matches found or API key limit reached. You can still input players below manually.")

# Fallback initializer
if 'player_data' not in st.session_state or not st.session_state.player_data:
    st.session_state.player_data = [
        {"Name": "Sample Player", "Role": "BAT", "Credits": 9.5, "Proj_Points": 50, "Team": "IND"}
    ]

# --- STEP 2: EDITING AND ADJUSTMENTS ---
st.subheader("📋 Active Player Pool & Stats")
st.write("The API loaded the players and roles! **Adjust the Credit values and Projected Points** below based on the toss, pitch report, or your strategy before running the math solver:")

df = pd.DataFrame(st.session_state.player_data)
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# --- STEP 3: OPTIMIZE ---
if st.button("🚀 Calculate Optimal Dream11 Team", type="primary"):
    if len(edited_df) < 11:
        st.error("The player pool needs at least 11 players to build a lineup.")
    else:
        prob = LpProblem("Dream11_Automated", LpMaximize)
        player_names = edited_df["Name"].tolist()
        player_vars = LpVariable.dicts("Select", player_names, cat="Binary")
        
        # Maximize projected points
        prob += lpSum([edited_df.loc[i, "Proj_Points"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index])
        
        # Constraints
        prob += lpSum([player_vars[name] for name in player_names]) == 11
        prob += lpSum([edited_df.loc[i, "Credits"] * player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index]) <= 100.0
        
        for role in ["WK", "BAT", "AR", "BOWL"]:
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == role]) >= 1
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Role"] == role]) <= 8
            
        for t in edited_df["Team"].unique():
            prob += lpSum([player_vars[edited_df.loc[i, "Name"]] for i in edited_df.index if edited_df.loc[i, "Team"] == t]) <= 10
            
        status = prob.solve(PULP_CBC_CMD(msg=False))
        
        if LpStatus[status] == "Optimal":
            selected = [name for name in player_names if player_vars[name].varValue == 1]
            result_df = edited_df[edited_df["Name"].isin(selected)].copy()
            result_df = result_df.sort_values(by="Proj_Points", ascending=False).reset_index(drop=True)
            
            st.subheader("🔥 Automated Dream11 Lineup")
            st.dataframe(result_df, use_container_width=True)
            
            st.metric("Total Credits Used", f"{result_df['Credits'].sum()} / 100")
            st.metric("Total Projected Points", f"{result_df['Proj_Points'].sum()}")
            
            if len(result_df) >= 2:
                st.info(f"👑 **Captain (2x Points):** {result_df.loc[0, 'Name']} ({result_df.loc[0, 'Role']})")
                st.info(f"✨ **Vice-Captain (1.5x Points):** {result_df.loc[1, 'Name']} ({result_df.loc[1, 'Role']})")
        else:
            st.error("No mathematical solution matches your credit constraints. Try lowering some credit values in the grid.")
