"""
Skylark Drones - SkyOps AI Coordinator
Main Streamlit Application
"""
import streamlit as st
import pandas as pd
import os
from data_engine import (
    load_data, query_pilots, query_drones, calculate_pilot_cost,
    update_pilot_status, update_drone_status, get_current_assignments,
    flag_maintenance_issues, match_pilots_to_mission, match_drones_to_mission,
    detect_all_conflicts, find_urgent_reassignment, get_full_summary,
    assign_pilot_to_mission, assign_drone_to_mission,
)
from agent import get_agent_response, parse_action, execute_action

# Try importing sheets sync (graceful if not configured)
try:
    from sheets_sync import (
        get_gspread_client, load_data_from_sheets,
        sync_pilot_status, sync_drone_status, full_sync_to_sheets,
    )
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# ─── PAGE CONFIG ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="SkyOps AI - Drone Operations Coordinator",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CUSTOM CSS ──────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    .status-available { color: #00cc66; font-weight: bold; }
    .status-assigned { color: #ff9900; font-weight: bold; }
    .status-leave { color: #ff4444; font-weight: bold; }
    .status-maintenance { color: #ff4444; font-weight: bold; }
    .conflict-card {
        background: #1a1a2e;
        border-left: 4px solid #ff4444;
        padding: 10px;
        margin: 5px 0;
        border-radius: 4px;
    }
    .success-card {
        background: #1a2e1a;
        border-left: 4px solid #00cc66;
        padding: 10px;
        margin: 5px 0;
        border-radius: 4px;
    }
    div[data-testid="stMetric"] {
        background-color: #1a1a2e;
        padding: 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ─── INITIALIZE SESSION STATE ────────────────────────────────────────

if "initialized" not in st.session_state:
    pilots, drones, missions = load_data()
    st.session_state.pilots = pilots
    st.session_state.drones = drones
    st.session_state.missions = missions
    st.session_state.chat_history = []
    st.session_state.action_log = []
    st.session_state.sheets_connected = False
    st.session_state.initialized = True


def get_data():
    return st.session_state.pilots, st.session_state.drones, st.session_state.missions


def save_data(pilots, drones, missions):
    st.session_state.pilots = pilots
    st.session_state.drones = drones
    st.session_state.missions = missions


def sync_to_sheets_if_connected(entity_type=None, entity_id=None, new_status=None, assignment=None):
    """Sync changes to Google Sheets if connected."""
    if not st.session_state.sheets_connected or not SHEETS_AVAILABLE:
        return
    try:
        client = get_gspread_client()
        sheet_id = st.secrets.get("spreadsheet_id", "")
        if not client or not sheet_id:
            return
        if entity_type == "pilot":
            sync_pilot_status(client, sheet_id, entity_id, new_status, assignment)
        elif entity_type == "drone":
            sync_drone_status(client, sheet_id, entity_id, new_status, assignment)
        elif entity_type == "full":
            pilots, drones, missions = get_data()
            full_sync_to_sheets(client, sheet_id, pilots, drones, missions)
    except Exception as e:
        st.toast(f"Sheets sync note: {e}", icon="⚠️")


# ─── SIDEBAR ─────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/drone.png", width=60)
    st.title("SkyOps AI")
    st.caption("Drone Operations Coordinator")
    st.divider()

    # API Key
    api_key = st.text_input("🔑 Groq API Key", type="password",value=st.secrets.get("groq_api_key", ""), 
                            help="Get free key at console.groq.com")
    
    st.divider()

    # Google Sheets Config
    st.subheader("📊 Google Sheets Sync")
    if SHEETS_AVAILABLE:
        try:
            sheet_id = st.secrets.get("spreadsheet_id", "")
            if sheet_id:
                st.success("✅ Sheets connected")
                st.session_state.sheets_connected = True
                if st.button("🔄 Sync from Sheets"):
                    client = get_gspread_client()
                    if client:
                        p, d, m = load_data_from_sheets(client, sheet_id)
                        if p is not None:
                            save_data(p, d, m)
                            st.success("Loaded from Sheets!")
                            st.rerun()
                if st.button("📤 Push to Sheets"):
                    sync_to_sheets_if_connected("full")
                    st.success("Pushed to Sheets!")
            else:
                st.info("Add spreadsheet_id to secrets")
        except Exception:
            st.info("Configure secrets.toml for Sheets sync")
    else:
        st.info("Sheets sync available when deployed")

    st.divider()

    # Quick actions
    st.subheader("⚡ Quick Actions")
    if st.button("🔍 Run Conflict Check", use_container_width=True):
        pilots, drones, missions = get_data()
        conflicts = detect_all_conflicts(pilots, drones, missions)
        st.session_state.last_conflicts = conflicts

    if st.button("🔧 Check Maintenance", use_container_width=True):
        _, drones, _ = get_data()
        issues = flag_maintenance_issues(drones)
        st.session_state.last_maintenance = issues

    if st.button("🔄 Reset Data", use_container_width=True):
        pilots, drones, missions = load_data()
        save_data(pilots, drones, missions)
        st.session_state.chat_history = []
        st.session_state.action_log = []
        st.success("Data reset to original!")
        st.rerun()

# ─── MAIN CONTENT ────────────────────────────────────────────────────

tab_chat, tab_dashboard, tab_pilots, tab_drones, tab_missions = st.tabs(
    ["💬 AI Chat", "📊 Dashboard", "👨‍✈️ Pilots", "🛩️ Drones", "📌 Missions"]
)

# ─── TAB: AI CHAT ────────────────────────────────────────────────────

with tab_chat:
    st.header("💬 SkyOps AI Coordinator")
    st.caption("Ask me anything about pilots, drones, missions, assignments, or conflicts!")

    # Example prompts
    with st.expander("💡 Example queries you can try"):
        st.markdown("""
- "Show me all available pilots in Bangalore"
- "Which drones can fly in rainy conditions?"
- "Match the best pilot for PRJ001"
- "What's the cost of assigning Arjun to PRJ001?"
- "Run a full conflict check"
- "Assign P001 to PRJ001"
- "Set P004 status to Available"
- "Find urgent reassignment options for PRJ002"
- "Which drone should we use for PRJ003?"
- "Show all current assignments"
- "Is P003 qualified for PRJ002?"
- "Flag any maintenance issues"
        """)

    # Chat display
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if user_input := st.chat_input("Ask SkyOps AI..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        if not api_key:
            response = "⚠️ Please enter your Gemini API key in the sidebar to use the AI chat. You can get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey)."
        else:
            pilots, drones, missions = get_data()
            data_context = get_full_summary(pilots, drones, missions)

            with st.spinner("🤖 SkyOps AI is thinking..."):
                # Build Gemini chat history format
                gemini_history = []
                for msg in st.session_state.chat_history[:-1]:  # exclude current
                    gemini_history.append({
                        "role": "user" if msg["role"] == "user" else "model",
                        "parts": [msg["content"]]
                    })

                response = get_agent_response(api_key, user_input, data_context, gemini_history)

            # Check for actions in response
            action = parse_action(response)
            if action:
                pilots, drones, missions, action_msg, entity_type = execute_action(
                    action, pilots, drones, missions
                )
                save_data(pilots, drones, missions)
                st.session_state.action_log.append(action_msg)

                # Sync to sheets
                if entity_type == "pilot":
                    pilot_id = action.get("args", {}).get("pilot_id")
                    new_status = action.get("args", {}).get("new_status", "Assigned")
                    assignment = action.get("args", {}).get("project_id")
                    sync_to_sheets_if_connected("pilot", pilot_id, new_status, assignment)
                elif entity_type == "drone":
                    drone_id = action.get("args", {}).get("drone_id")
                    new_status = action.get("args", {}).get("new_status", "Assigned")
                    assignment = action.get("args", {}).get("project_id")
                    sync_to_sheets_if_connected("drone", drone_id, new_status, assignment)

                response += f"\n\n---\n🔧 **Action Executed:** {action_msg}"

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

# ─── TAB: DASHBOARD ──────────────────────────────────────────────────

with tab_dashboard:
    st.header("📊 Operations Dashboard")
    pilots, drones, missions = get_data()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avail_pilots = len(pilots[pilots["status"] == "Available"])
        st.metric("Available Pilots", f"{avail_pilots}/{len(pilots)}")
    with col2:
        avail_drones = len(drones[drones["status"] == "Available"])
        st.metric("Available Drones", f"{avail_drones}/{len(drones)}")
    with col3:
        active = len(missions[missions["priority"] == "Urgent"])
        st.metric("Urgent Missions", active)
    with col4:
        conflicts = detect_all_conflicts(pilots, drones, missions)
        real_conflicts = [c for c in conflicts if not c.startswith("✅")]
        st.metric("Active Conflicts", len(real_conflicts))

    st.divider()

    # Conflicts
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("⚠️ Conflict Report")
        if hasattr(st.session_state, "last_conflicts"):
            for c in st.session_state.last_conflicts:
                if c.startswith("✅"):
                    st.success(c)
                elif "🔴" in c:
                    st.error(c)
                else:
                    st.warning(c)
        else:
            for c in conflicts:
                if c.startswith("✅"):
                    st.success(c)
                elif "🔴" in c:
                    st.error(c)
                else:
                    st.warning(c)

    with col_right:
        st.subheader("🔧 Maintenance Alerts")
        maint = flag_maintenance_issues(drones)
        for m in maint:
            if m.startswith("✅"):
                st.success(m)
            elif "⚠️" in m:
                st.error(m)
            else:
                st.warning(m)

    st.divider()

    # Action Log
    if st.session_state.action_log:
        st.subheader("📝 Action Log")
        for log in reversed(st.session_state.action_log[-10:]):
            st.info(log)


# ─── TAB: PILOTS ─────────────────────────────────────────────────────

with tab_pilots:
    st.header("👨‍✈️ Pilot Roster")
    pilots, drones, missions = get_data()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        skill_filter = st.selectbox("Filter by Skill", ["All", "Mapping", "Survey", "Inspection", "Thermal"])
    with col2:
        loc_filter = st.selectbox("Filter by Location", ["All", "Bangalore", "Mumbai"])
    with col3:
        status_filter = st.selectbox("Filter by Status", ["All", "Available", "Assigned", "On Leave", "Unavailable"])

    filtered = pilots.copy()
    if skill_filter != "All":
        filtered = filtered[filtered["skills"].str.contains(skill_filter, case=False)]
    if loc_filter != "All":
        filtered = filtered[filtered["location"] == loc_filter]
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    # Update Status
    st.subheader("✏️ Update Pilot Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        pid = st.selectbox("Select Pilot", pilots["pilot_id"].tolist(),
                           format_func=lambda x: f"{x} - {pilots[pilots['pilot_id']==x]['name'].values[0]}")
    with col2:
        new_status = st.selectbox("New Status", ["Available", "Assigned", "On Leave", "Unavailable"], key="pilot_status")
    with col3:
        if st.button("Update Pilot Status", type="primary"):
            pilots, msg = update_pilot_status(pilots, pid, new_status)
            save_data(pilots, drones, missions)
            sync_to_sheets_if_connected("pilot", pid, new_status)
            st.success(msg)
            st.session_state.action_log.append(msg)
            st.rerun()

    # Cost Calculator
    st.subheader("💰 Cost Calculator")
    col1, col2, col3 = st.columns(3)
    with col1:
        cost_pid = st.selectbox("Pilot", pilots["pilot_id"].tolist(), key="cost_pilot",
                                format_func=lambda x: f"{x} - {pilots[pilots['pilot_id']==x]['name'].values[0]}")
    with col2:
        cost_proj = st.selectbox("Mission", missions["project_id"].tolist(), key="cost_mission")
    with col3:
        if st.button("Calculate Cost"):
            m = missions[missions["project_id"] == cost_proj].iloc[0]
            total, msg = calculate_pilot_cost(pilots, cost_pid, m["start_date"], m["end_date"])
            if total:
                budget = m["mission_budget_inr"]
                if total > budget:
                    st.error(f"{msg}\n⚠️ OVER BUDGET by ₹{total - budget} (budget: ₹{budget})")
                else:
                    st.success(f"{msg}\n✅ Within budget (₹{budget})")


# ─── TAB: DRONES ─────────────────────────────────────────────────────

with tab_drones:
    st.header("🛩️ Drone Fleet")
    pilots, drones, missions = get_data()

    col1, col2 = st.columns(2)
    with col1:
        cap_filter = st.selectbox("Filter by Capability", ["All", "LiDAR", "RGB", "Thermal"])
    with col2:
        drone_status_filter = st.selectbox("Filter by Status", ["All", "Available", "Assigned", "Maintenance"], key="drone_st")

    filtered_d = drones.copy()
    if cap_filter != "All":
        filtered_d = filtered_d[filtered_d["capabilities"].str.contains(cap_filter, case=False)]
    if drone_status_filter != "All":
        filtered_d = filtered_d[filtered_d["status"] == drone_status_filter]

    st.dataframe(filtered_d, use_container_width=True, hide_index=True)

    # Update Status
    st.subheader("✏️ Update Drone Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        did = st.selectbox("Select Drone", drones["drone_id"].tolist(),
                           format_func=lambda x: f"{x} - {drones[drones['drone_id']==x]['model'].values[0]}")
    with col2:
        new_d_status = st.selectbox("New Status", ["Available", "Assigned", "Maintenance"], key="drone_status_update")
    with col3:
        if st.button("Update Drone Status", type="primary"):
            drones, msg = update_drone_status(drones, did, new_d_status)
            save_data(pilots, drones, missions)
            sync_to_sheets_if_connected("drone", did, new_d_status)
            st.success(msg)
            st.session_state.action_log.append(msg)
            st.rerun()

    # Weather Compatibility
    st.subheader("🌧️ Weather Compatibility")
    for _, d in drones.iterrows():
        if "ip43" in d["weather_resistance"].lower():
            st.success(f"✅ {d['drone_id']} ({d['model']}) - Rain rated ({d['weather_resistance']})")
        else:
            st.warning(f"⚠️ {d['drone_id']} ({d['model']}) - Clear sky only ({d['weather_resistance']})")


# ─── TAB: MISSIONS ───────────────────────────────────────────────────

with tab_missions:
    st.header("📌 Missions")
    pilots, drones, missions = get_data()

    st.dataframe(missions, use_container_width=True, hide_index=True)

    st.divider()

    # Mission Matching
    st.subheader("🎯 Smart Assignment Matching")
    selected_mission = st.selectbox("Select Mission", missions["project_id"].tolist(),
                                     format_func=lambda x: f"{x} - {missions[missions['project_id']==x]['client'].values[0]} ({missions[missions['project_id']==x]['location'].values[0]})")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**👨‍✈️ Pilot Matches**")
        if st.button("Find Best Pilots"):
            candidates, msg = match_pilots_to_mission(pilots, missions, selected_mission)
            for c in candidates:
                icon = "✅" if "Perfect" in c["fit"] else ("⚠️" if "Partial" in c["fit"] else "❌")
                issues = ", ".join(c["issues"]) if c["issues"] else "No issues"
                st.markdown(f"{icon} **{c['name']}** ({c['pilot_id']}) - {c['fit']} - ₹{c['total_cost']}")
                st.caption(f"  Issues: {issues}")

    with col2:
        st.markdown("**🛩️ Drone Matches**")
        if st.button("Find Best Drones"):
            candidates, msg = match_drones_to_mission(drones, missions, selected_mission)
            for c in candidates:
                icon = "✅" if "Perfect" in c["fit"] else ("⚠️" if "Partial" in c["fit"] else "❌")
                issues = ", ".join(c["issues"]) if c["issues"] else "No issues"
                st.markdown(f"{icon} **{c['model']}** ({c['drone_id']}) - {c['fit']}")
                st.caption(f"  Issues: {issues}")

    st.divider()

    # Direct Assignment
    st.subheader("📋 Quick Assign")
    col1, col2, col3 = st.columns(3)
    with col1:
        assign_mission = st.selectbox("Mission", missions["project_id"].tolist(), key="assign_m")
    with col2:
        assign_pilot = st.selectbox("Assign Pilot", ["None"] + pilots["pilot_id"].tolist(), key="assign_p",
                                     format_func=lambda x: x if x == "None" else f"{x} - {pilots[pilots['pilot_id']==x]['name'].values[0]}")
    with col3:
        assign_drone = st.selectbox("Assign Drone", ["None"] + drones["drone_id"].tolist(), key="assign_d",
                                     format_func=lambda x: x if x == "None" else f"{x} - {drones[drones['drone_id']==x]['model'].values[0]}")

    if st.button("Execute Assignment", type="primary"):
        msgs = []
        if assign_pilot != "None":
            pilots, msg = assign_pilot_to_mission(pilots, assign_pilot, assign_mission, missions)
            msgs.append(msg)
            sync_to_sheets_if_connected("pilot", assign_pilot, "Assigned", assign_mission)
        if assign_drone != "None":
            drones, msg = assign_drone_to_mission(drones, assign_drone, assign_mission, missions)
            msgs.append(msg)
            sync_to_sheets_if_connected("drone", assign_drone, "Assigned", assign_mission)
        save_data(pilots, drones, missions)
        for m in msgs:
            st.success(m)
            st.session_state.action_log.append(m)

        # Auto conflict check after assignment
        conflicts = detect_all_conflicts(pilots, drones, missions)
        real_conflicts = [c for c in conflicts if not c.startswith("✅")]
        if real_conflicts:
            st.warning("⚠️ Conflicts detected after assignment:")
            for c in real_conflicts:
                st.error(c)

    # Urgent Reassignment
    st.divider()
    st.subheader("🚨 Urgent Reassignment")
    reassign_mission = st.selectbox("Mission needing reassignment", missions["project_id"].tolist(), key="reassign_m")
    if st.button("Generate Reassignment Plan", type="secondary"):
        result = find_urgent_reassignment(pilots, drones, missions, reassign_mission)
        st.text(result)


# ─── FOOTER ──────────────────────────────────────────────────────────

st.divider()
st.caption("SkyOps AI v1.0 | Built for Skylark Drones | Powered by Groq (LLaMA 3.3) + Streamlit")
