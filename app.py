import streamlit as st
import pandas as pd
from pulp import (
    LpProblem,
    LpMaximize,
    LpVariable,
    lpSum,
    PULP_CBC_CMD,
    LpStatus,
)

st.set_page_config(
    page_title="Dream11 Unique Team & Captain Builder",
    layout="centered",
)

st.title("🏏 Dream11 Unique Team & Captain Builder")
st.write(
    "Add 22 players: 11 from Team A and 11 from Team B. "
    "Generate the maximum number of unique 11-player combinations, "
    "then choose Captain and Vice-Captain for every team."
)

ROLES = ["WK", "BAT", "AR", "BOWL"]
TEAM_OPTIONS = ["Team A", "Team B"]

# ----------------------------
# Session state
# ----------------------------
if "player_data" not in st.session_state:
    st.session_state.player_data = []

if "captain_selections" not in st.session_state:
    st.session_state.captain_selections = {}

if "vice_captain_selections" not in st.session_state:
    st.session_state.vice_captain_selections = {}

# ----------------------------
# Add player form
# ----------------------------
st.subheader("➕ Add Player to Pool")

with st.form("add_player_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        p_name = st.text_input("Player Name")
        p_role = st.selectbox("Role / Position", ROLES)

    with col2:
        p_team = st.selectbox("Original Team", TEAM_OPTIONS)
        p_credits = st.number_input(
            "Credits cost",
            min_value=1.0,
            max_value=20.0,
            value=9.0,
            step=0.5,
        )

    with col3:
        st.write("")
        st.write("")
        submitted = st.form_submit_button("Add Player")

    if submitted:
        if p_name.strip():
            st.session_state.player_data.append(
                {
                    "Name": p_name.strip(),
                    "Role": p_role,
                    "Team": p_team,
                    "Credits": float(p_credits),
                    "Lock_In_All_Teams": False,
                }
            )
            st.success(f"Added {p_name.strip()} to the pool!")
        else:
            st.error("Please enter a player name.")

# ----------------------------
# Player pool editor
# ----------------------------
st.subheader("📋 Your Custom Player Pool")

if len(st.session_state.player_data) == 0:
    st.info("Your pool is empty. Use the form above to add players.")

    player_df = pd.DataFrame(
        columns=[
            "Name",
            "Role",
            "Team",
            "Credits",
            "Lock_In_All_Teams",
        ]
    )
else:
    player_df = pd.DataFrame(st.session_state.player_data)
    player_df = player_df[
        [
            "Name",
            "Role",
            "Team",
            "Credits",
            "Lock_In_All_Teams",
        ]
    ]

edited_df = st.data_editor(
    player_df,
    num_rows="dynamic",
    use_container_width=True,
    key="player_pool_editor",
)

st.session_state.player_data = edited_df.to_dict("records")

# ----------------------------
# Strategy mode
# ----------------------------
st.subheader("🛠️ Choose Strategy Mode")

optimizer_mode = st.radio(
    "Select which strategy rule to enforce for this generation:",
    [
        "🔀 Two-Team Combination Mode (Recommended)",
        "🔒 Lock Mode (Force specific players into all teams)",
        "🎛️ Sliders Mode (Enforce exact position counts)",
    ],
    index=0,
)

team_a_count = 6
team_b_count = 5

target_wk = 1
target_bat = 3
target_ar = 3
target_bowl = 4

if "🔀 Two-Team Combination Mode" in optimizer_mode:

    st.info(
        "💡 **Active Strategy:** Choose how many players to take from "
        "Team A and Team B. Every generated team will contain exactly "
        "11 players within 100 credits."
    )

    split_option = st.selectbox(
        "Choose Team A + Team B split:",
        [
            "6 from Team A + 5 from Team B",
            "5 from Team A + 6 from Team B",
            "7 from Team A + 4 from Team B",
            "4 from Team A + 7 from Team B",
            "8 from Team A + 3 from Team B",
            "3 from Team A + 8 from Team B",
        ],
        index=0,
    )

    split_map = {
        "6 from Team A + 5 from Team B": (6, 5),
        "5 from Team A + 6 from Team B": (5, 6),
        "7 from Team A + 4 from Team B": (7, 4),
        "4 from Team A + 7 from Team B": (4, 7),
        "8 from Team A + 3 from Team B": (8, 3),
        "3 from Team A + 8 from Team B": (3, 8),
    }

    team_a_count, team_b_count = split_map[split_option]

    st.success(
        f"Each generated team will contain "
        f"**{team_a_count} players from Team A** and "
        f"**{team_b_count} players from Team B**."
    )

elif "🔒 Lock Mode" in optimizer_mode:
    st.info(
        "💡 **Active Strategy:** The engine will force your selected "
        "'Lock' players into all lineups and automatically balance the "
        "remaining slots using Dream11 standard rules."
    )

else:
    st.info(
        "💡 **Active Strategy:** The engine will ignore lock checkboxes "
        "and build lineups matching your exact slider combination below."
    )

    col_wk, col_bat = st.columns(2)

    with col_wk:
        target_wk = st.slider(
            "Wicket-Keepers (WK) wanted:",
            min_value=1,
            max_value=8,
            value=1,
        )

    with col_bat:
        target_bat = st.slider(
            "Batsmen (BAT) wanted:",
            min_value=1,
            max_value=8,
            value=3,
        )

    col_ar, col_bowl = st.columns(2)

    with col_ar:
        target_ar = st.slider(
            "All-Rounders (AR) wanted:",
            min_value=1,
            max_value=8,
            value=3,
        )

    with col_bowl:
        target_bowl = st.slider(
            "Bowlers (BOWL) wanted:",
            min_value=1,
            max_value=8,
            value=4,
        )

    total_requested_slots = (
        target_wk + target_bat + target_ar + target_bowl
    )

    st.info(
        f"Total slots chosen per team: **{total_requested_slots} / 11**"
    )

# ----------------------------
# Uniqueness setting
# ----------------------------
st.subheader("🔁 Unique Team Strength")

max_overlap = st.selectbox(
    "Maximum players allowed to repeat from any previous team:",
    [
        "Allow up to 8 same players",
        "Allow up to 7 same players",
        "Allow up to 6 same players",
        "Allow up to 5 same players",
    ],
    index=0,
)

overlap_map = {
    "Allow up to 8 same players": 8,
    "Allow up to 7 same players": 7,
    "Allow up to 6 same players": 6,
    "Allow up to 5 same players": 5,
}

max_allowed_overlap = overlap_map[max_overlap]

if max_allowed_overlap == 8:
    st.info(
        "This creates the maximum number of teams, but teams may be "
        "similar. Each new team will differ by at least 3 players."
    )
elif max_allowed_overlap == 7:
    st.info(
        "Each new team will differ by at least 4 players from every "
        "previous team."
    )
elif max_allowed_overlap == 6:
    st.info(
        "Each new team will differ by at least 5 players from every "
        "previous team."
    )
else:
    st.info(
        "This creates the most different teams, but fewer teams may be "
        "possible. Each new team will differ by at least 6 players."
    )

# ----------------------------
# Generation settings
# ----------------------------
st.subheader("🤖 Generation Settings")

num_teams_to_gen = st.number_input(
    "Maximum number of unique teams to generate:",
    min_value=1,
    max_value=40,
    value=20,
    step=1,
)

st.caption(
    "The app will keep generating until it reaches this limit or no more "
    "valid unique combinations are possible."
)

# ----------------------------
# Generate teams
# ----------------------------
if st.button("🚀 Generate Maximum Unique Teams", type="primary"):

    # Clear previous captain selections when generating new teams
    st.session_state.captain_selections = {}
    st.session_state.vice_captain_selections = {}

    cleaned_df = edited_df.dropna(subset=["Name"]).copy()
    cleaned_df = cleaned_df[
        cleaned_df["Name"].astype(str).str.strip() != ""
    ].copy()
    cleaned_df = cleaned_df.reset_index(drop=True)

    if len(cleaned_df) < 11:
        st.error("You need at least 11 valid players to generate a squad.")
        st.stop()

    cleaned_df["Credits"] = pd.to_numeric(
        cleaned_df["Credits"],
        errors="coerce",
    ).fillna(0.0)

    cleaned_df["Lock_In_All_Teams"] = (
        cleaned_df["Lock_In_All_Teams"]
        .fillna(False)
        .astype(bool)
    )

    cleaned_df["Team"] = cleaned_df["Team"].fillna("Team A")

    total_locked = int(cleaned_df["Lock_In_All_Teams"].sum())

    team_a_players = cleaned_df[cleaned_df["Team"] == "Team A"]
    team_b_players = cleaned_df[cleaned_df["Team"] == "Team B"]

    if "🔀 Two-Team Combination Mode" in optimizer_mode:

        if len(team_a_players) < team_a_count:
            st.error(
                f"You need at least {team_a_count} players marked as "
                f"Team A. You currently have {len(team_a_players)}."
            )
            st.stop()

        if len(team_b_players) < team_b_count:
            st.error(
                f"You need at least {team_b_count} players marked as "
                f"Team B. You currently have {len(team_b_players)}."
            )
            st.stop()

    elif "🎛️ Sliders Mode" in optimizer_mode:
        total_requested_slots = (
            target_wk + target_bat + target_ar + target_bowl
        )

        if total_requested_slots != 11:
            st.error(
                f"Your sliders add up to {total_requested_slots} players. "
                "They must add up to exactly 11 players."
            )
            st.stop()

    else:
        if total_locked > 11:
            st.error(
                f"You have locked {total_locked} players. "
                "You cannot lock more than 11 players into a team."
            )
            st.stop()

    generated_lineups = []
    previous_teams = []

    with st.spinner("Generating maximum unique teams..."):

        for team_number in range(1, num_teams_to_gen + 1):

            prob = LpProblem(
                f"Dream11_Unique_Team_{team_number}",
                LpMaximize,
            )

            player_vars = {
                str(i): LpVariable(f"choice_{i}", cat="Binary")
                for i in cleaned_df.index
            }

            # Objective: maximize credits used while remaining under 100
            prob += lpSum(
                cleaned_df.loc[i, "Credits"] * player_vars[str(i)]
                for i in cleaned_df.index
            )

            # Exactly 11 players
            prob += lpSum(
                player_vars[str(i)]
                for i in cleaned_df.index
            ) == 11

            # Maximum 100 credits
            prob += lpSum(
                cleaned_df.loc[i, "Credits"] * player_vars[str(i)]
                for i in cleaned_df.index
            ) <= 100.0

            if "🔀 Two-Team Combination Mode" in optimizer_mode:

                prob += lpSum(
                    player_vars[str(i)]
                    for i in cleaned_df.index
                    if cleaned_df.loc[i, "Team"] == "Team A"
                ) == team_a_count

                prob += lpSum(
                    player_vars[str(i)]
                    for i in cleaned_df.index
                    if cleaned_df.loc[i, "Team"] == "Team B"
                ) == team_b_count

                for role in ROLES:
                    role_count = lpSum(
                        player_vars[str(i)]
                        for i in cleaned_df.index
                        if cleaned_df.loc[i, "Role"] == role
                    )

                    prob += role_count >= 1
                    prob += role_count <= 8

            elif "🎛️ Sliders Mode" in optimizer_mode:

                role_targets = {
                    "WK": target_wk,
                    "BAT": target_bat,
                    "AR": target_ar,
                    "BOWL": target_bowl,
                }

                for role, target in role_targets.items():
                    prob += lpSum(
                        player_vars[str(i)]
                        for i in cleaned_df.index
                        if cleaned_df.loc[i, "Role"] == role
                    ) == target

            else:

                for role in ROLES:
                    role_count = lpSum(
                        player_vars[str(i)]
                        for i in cleaned_df.index
                        if cleaned_df.loc[i, "Role"] == role
                    )

                    prob += role_count >= 1
                    prob += role_count <= 8

                for i in cleaned_df.index:
                    if bool(cleaned_df.loc[i, "Lock_In_All_Teams"]):
                        prob += player_vars[str(i)] == 1

            # Force uniqueness against every previously generated team
            for previous_team in previous_teams:
                prob += lpSum(
                    player_vars[str(i)]
                    for i in previous_team
                ) <= max_allowed_overlap

            status = prob.solve(PULP_CBC_CMD(msg=False))

            if LpStatus[status] != "Optimal":
                if team_number == 1:
                    st.error(
                        "No valid combination matches your selected strategy. "
                        "Check credits, roles, teams, locks, split, or "
                        "uniqueness setting."
                    )
                else:
                    st.warning(
                        f"Generated the maximum possible number of unique "
                        f"teams for your settings: "
                        f"**{len(generated_lineups)} teams**."
                    )
                break

            selected_indices = [
                i
                for i in cleaned_df.index
                if player_vars[str(i)].varValue == 1
            ]

            previous_teams.append(selected_indices)

            team_df = cleaned_df.loc[selected_indices].copy()
            team_df = team_df.drop(columns=["Lock_In_All_Teams"])
            team_df = team_df.reset_index(drop=True)

            generated_lineups.append((team_number, team_df))

    if generated_lineups:
        st.success(
            f"Successfully generated **{len(generated_lineups)} unique "
            "team lineups!** Now choose Captain and Vice-Captain below."
        )

        for team_number, team_df in generated_lineups:
            credits_used = team_df["Credits"].sum()
            player_names = team_df["Name"].tolist()

            team_a_selected = int((team_df["Team"] == "Team A").sum())
            team_b_selected = int((team_df["Team"] == "Team B").sum())

            with st.expander(
                f"📋 TEAM {team_number} | "
                f"Team A: {team_a_selected} | Team B: {team_b_selected} | "
                f"Credits: {credits_used:.1f} / 100"
            ):
                st.dataframe(team_df, use_container_width=True)

                captain_key = f"captain_team_{team_number}"
                vice_captain_key = f"vice_captain_team_{team_number}"

                col_cap, col_vice = st.columns(2)

                with col_cap:
                    captain = st.selectbox(
                        "👑 Choose Captain",
                        player_names,
                        key=captain_key,
                    )

                with col_vice:
                    default_index = 0
                    if captain in player_names:
                        default_index = (
                            player_names.index(captain) + 1
                        ) % len(player_names)

                    vice_captain = st.selectbox(
                        "✨ Choose Vice-Captain",
                        player_names,
                        index=default_index,
                        key=vice_captain_key,
                    )

                if captain == vice_captain:
                    st.error(
                        "Captain and Vice-Captain cannot be the same player."
                    )
                else:
                    st.success(
                        f"👑 **Captain:** {captain} | "
                        f"✨ **Vice-Captain:** {vice_captain}"
                    )

                    st.session_state.captain_selections[team_number] = captain
                    st.session_state.vice_captain_selections[team_number] = (
                        vice_captain
                    )
