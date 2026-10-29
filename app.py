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
    page_title="Dream11 Dual-Mode Optimizer",
    layout="centered",
)

st.title("🏏 Dream11 Multi-Team Builder")
st.write(
    "Add your 22-24 players manually. Choose either Player Lock mode or "
    "Target Sliders mode to build up to 40 unique team variations."
)

ROLES = ["WK", "BAT", "AR", "BOWL"]

# ----------------------------
# Session state
# ----------------------------
if "player_data" not in st.session_state:
    st.session_state.player_data = []

# ----------------------------
# Add player form
# ----------------------------
st.subheader("➕ Add Player to Pool")

with st.form("add_player_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        p_name = st.text_input("Player Name")
        p_role = st.selectbox("Role / Position", ROLES)

    with col2:
        p_credits = st.number_input(
            "Credits cost",
            min_value=1.0,
            max_value=20.0,
            value=9.0,
            step=0.5,
        )

    submitted = st.form_submit_button("Add Player")

    if submitted:
        if p_name.strip():
            st.session_state.player_data.append(
                {
                    "Name": p_name.strip(),
                    "Role": p_role,
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
        columns=["Name", "Role", "Credits", "Lock_In_All_Teams"]
    )
else:
    player_df = pd.DataFrame(st.session_state.player_data)
    player_df = player_df[
        ["Name", "Role", "Credits", "Lock_In_All_Teams"]
    ]

edited_df = st.data_editor(
    player_df,
    num_rows="dynamic",
    use_container_width=True,
    key="player_pool_editor",
)

# Save edits back to session state
st.session_state.player_data = edited_df.to_dict("records")

# ----------------------------
# Strategy mode
# ----------------------------
st.subheader("🛠️ Choose Strategy Mode")

optimizer_mode = st.radio(
    "Select which strategy rule to enforce for this generation:",
    [
        "🔒 Lock Mode (Force specific players into all teams)",
        "🎛️ Sliders Mode (Enforce exact position counts)",
    ],
    index=0,
)

target_wk = 1
target_bat = 3
target_ar = 3
target_bowl = 4

if "🔒 Lock Mode" in optimizer_mode:
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
# Generation settings
# ----------------------------
st.subheader("🤖 Generation Settings")

num_teams_to_gen = st.number_input(
    "How many unique teams do you want to generate?",
    min_value=1,
    max_value=40,
    value=10,
    step=1,
)

# ----------------------------
# Generate teams
# ----------------------------
if st.button("🚀 Generate Teams", type="primary"):

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

    total_locked = int(cleaned_df["Lock_In_All_Teams"].sum())

    if "🎛️ Sliders Mode" in optimizer_mode:
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

    with st.spinner("Generating unique teams..."):

        for team_number in range(1, num_teams_to_gen + 1):

            prob = LpProblem(
                f"Dream11_Team_{team_number}",
                LpMaximize,
            )

            # Version-safe binary decision variables
            player_vars = {
                str(i): LpVariable(f"choice_{i}", cat="Binary")
                for i in cleaned_df.index
            }

            # Objective: use maximum credits without exceeding 100
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

            if "🎛️ Sliders Mode" in optimizer_mode:

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

            # Make each new team different from previous teams.
            # A new team can share maximum 8 players with any earlier team.
            for previous_team in previous_teams:
                prob += lpSum(
                    player_vars[str(i)]
                    for i in previous_team
                ) <= 8

            status = prob.solve(PULP_CBC_CMD(msg=False))

            if LpStatus[status] != "Optimal":
                if team_number == 1:
                    st.error(
                        "No valid combination matches your selected strategy. "
                        "Check player credits, roles, locks, or slider values."
                    )
                else:
                    st.warning(
                        f"Could only generate {len(generated_lineups)} "
                        "unique teams before running out of valid combinations."
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
            f"Successfully generated {len(generated_lineups)} "
            "unique team lineups!"
        )

        for team_number, team_df in generated_lineups:
            credits_used = team_df["Credits"].sum()

            with st.expander(
                f"📋 TEAM {team_number} "
                f"(Total Credits Used: {credits_used:.1f} / 100)"
            ):
                st.dataframe(team_df, use_container_width=True)

                if len(team_df) >= 2:
                    st.info(
                        f"👑 **Captain:** {team_df.loc[0, 'Name']} | "
                        f"✨ **Vice-Captain:** {team_df.loc[1, 'Name']}"
                    )
