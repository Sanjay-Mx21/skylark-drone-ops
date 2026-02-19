"""
Skylark Drones - Core Data Engine
Handles all data operations, conflict detection, and matching logic.
"""
import pandas as pd
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_data():
    """Load all CSVs into DataFrames."""
    pilots = pd.read_csv(os.path.join(DATA_DIR, "pilot_roster.csv"))
    drones = pd.read_csv(os.path.join(DATA_DIR, "drone_fleet.csv"))
    missions = pd.read_csv(os.path.join(DATA_DIR, "missions.csv"))

    # Clean whitespace from string columns
    for df in [pilots, drones, missions]:
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()

    return pilots, drones, missions


# ─── ROSTER MANAGEMENT ───────────────────────────────────────────────

def query_pilots(pilots, skill=None, certification=None, location=None, status=None):
    """Filter pilots by skill, certification, location, status."""
    result = pilots.copy()
    if skill:
        result = result[result["skills"].str.contains(skill, case=False, na=False)]
    if certification:
        result = result[result["certifications"].str.contains(certification, case=False, na=False)]
    if location:
        result = result[result["location"].str.contains(location, case=False, na=False)]
    if status:
        result = result[result["status"].str.contains(status, case=False, na=False)]
    return result


def calculate_pilot_cost(pilots, pilot_id, start_date, end_date):
    """Calculate total cost for a pilot over a mission duration."""
    pilot = pilots[pilots["pilot_id"] == pilot_id]
    if pilot.empty:
        return None, f"Pilot {pilot_id} not found."
    pilot = pilot.iloc[0]
    start = date_parser.parse(start_date)
    end = date_parser.parse(end_date)
    days = (end - start).days + 1  # inclusive
    total = days * pilot["daily_rate_inr"]
    return total, f"{pilot['name']} @ ₹{pilot['daily_rate_inr']}/day × {days} days = ₹{total}"


def update_pilot_status(pilots, pilot_id, new_status):
    """Update a pilot's status. Returns updated df."""
    valid = ["Available", "Assigned", "On Leave", "Unavailable"]
    if new_status not in valid:
        return pilots, f"Invalid status. Choose from: {valid}"
    idx = pilots.index[pilots["pilot_id"] == pilot_id]
    if idx.empty:
        return pilots, f"Pilot {pilot_id} not found."
    pilots.loc[idx, "status"] = new_status
    name = pilots.loc[idx, "name"].values[0]
    return pilots, f"✅ {name} ({pilot_id}) status updated to '{new_status}'."


def get_current_assignments(pilots):
    """Show pilots currently assigned to projects."""
    assigned = pilots[pilots["status"] == "Assigned"]
    if assigned.empty:
        return "No pilots currently assigned."
    return assigned[["pilot_id", "name", "current_assignment", "location"]].to_string(index=False)


# ─── DRONE INVENTORY ─────────────────────────────────────────────────

def query_drones(drones, capability=None, status=None, location=None, weather_ok=None):
    """Filter drones by capability, status, location, weather resistance."""
    result = drones.copy()
    if capability:
        result = result[result["capabilities"].str.contains(capability, case=False, na=False)]
    if status:
        result = result[result["status"].str.contains(status, case=False, na=False)]
    if location:
        result = result[result["location"].str.contains(location, case=False, na=False)]
    if weather_ok and weather_ok.lower() == "rainy":
        result = result[result["weather_resistance"].str.contains("IP43", case=False, na=False)]
    return result


def flag_maintenance_issues(drones):
    """Flag drones with upcoming or overdue maintenance."""
    today = datetime.now().date()
    issues = []
    for _, d in drones.iterrows():
        due = date_parser.parse(d["maintenance_due"]).date()
        if due <= today:
            issues.append(f"⚠️ {d['drone_id']} ({d['model']}): Maintenance OVERDUE (was due {d['maintenance_due']})")
        elif due <= today + timedelta(days=7):
            issues.append(f"🔔 {d['drone_id']} ({d['model']}): Maintenance due soon ({d['maintenance_due']})")
    return issues if issues else ["✅ No maintenance issues flagged."]


def update_drone_status(drones, drone_id, new_status):
    """Update drone status."""
    valid = ["Available", "Assigned", "Maintenance"]
    if new_status not in valid:
        return drones, f"Invalid status. Choose from: {valid}"
    idx = drones.index[drones["drone_id"] == drone_id]
    if idx.empty:
        return drones, f"Drone {drone_id} not found."
    drones.loc[idx, "status"] = new_status
    model = drones.loc[idx, "model"].values[0]
    return drones, f"✅ {drone_id} ({model}) status updated to '{new_status}'."


# ─── ASSIGNMENT MATCHING ─────────────────────────────────────────────

def match_pilots_to_mission(pilots, missions, project_id):
    """Find best pilot matches for a mission based on requirements."""
    mission = missions[missions["project_id"] == project_id]
    if mission.empty:
        return [], f"Mission {project_id} not found."
    m = mission.iloc[0]

    required_skills = [s.strip() for s in m["required_skills"].split(",")]
    required_certs = [c.strip() for c in m["required_certs"].split(",")]
    mission_location = m["location"]
    budget = m["mission_budget_inr"]
    start = date_parser.parse(m["start_date"])
    end = date_parser.parse(m["end_date"])
    days = (end - start).days + 1

    candidates = []
    for _, p in pilots.iterrows():
        issues = []
        score = 0

        # Skill check
        pilot_skills = [s.strip() for s in p["skills"].split(",")]
        has_skills = all(rs.lower() in [ps.lower() for ps in pilot_skills] for rs in required_skills)
        if has_skills:
            score += 3
        else:
            issues.append(f"Missing skill(s): {[s for s in required_skills if s.lower() not in [ps.lower() for ps in pilot_skills]]}")

        # Cert check
        pilot_certs = [c.strip() for c in p["certifications"].split(",")]
        has_certs = all(rc.lower() in [pc.lower() for pc in pilot_certs] for rc in required_certs)
        if has_certs:
            score += 3
        else:
            issues.append(f"Missing cert(s): {[c for c in required_certs if c.lower() not in [pc.lower() for pc in pilot_certs]]}")

        # Location check
        if p["location"].lower() == mission_location.lower():
            score += 2
        else:
            issues.append(f"Location mismatch: pilot in {p['location']}, mission in {mission_location}")

        # Availability check
        if p["status"] == "Available":
            score += 2
        elif p["status"] == "On Leave":
            avail = date_parser.parse(p["available_from"]).date()
            if avail <= start.date():
                score += 1
                issues.append(f"On leave until {p['available_from']}, but available before mission start")
            else:
                issues.append(f"On leave until {p['available_from']} (after mission start {m['start_date']})")
        else:
            issues.append(f"Status: {p['status']}")

        # Budget check
        total_cost = days * p["daily_rate_inr"]
        if total_cost <= budget:
            score += 2
        else:
            issues.append(f"Over budget: ₹{total_cost} > ₹{budget} budget")

        candidates.append({
            "pilot_id": p["pilot_id"],
            "name": p["name"],
            "score": score,
            "total_cost": total_cost,
            "issues": issues,
            "fit": "✅ Perfect" if score >= 10 else ("⚠️ Partial" if score >= 6 else "❌ Poor")
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, f"Found {len(candidates)} candidates for {project_id}."


def match_drones_to_mission(drones, missions, project_id):
    """Find best drone matches based on weather and capabilities."""
    mission = missions[missions["project_id"] == project_id]
    if mission.empty:
        return [], f"Mission {project_id} not found."
    m = mission.iloc[0]

    weather = m["weather_forecast"]
    mission_location = m["location"]
    required_skills = [s.strip().lower() for s in m["required_skills"].split(",")]

    # Map skills to drone capabilities
    skill_to_cap = {
        "mapping": ["lidar", "rgb"],
        "survey": ["lidar", "rgb"],
        "inspection": ["rgb"],
        "thermal": ["thermal"],
    }
    needed_caps = set()
    for skill in required_skills:
        if skill in skill_to_cap:
            needed_caps.update(skill_to_cap[skill])

    candidates = []
    for _, d in drones.iterrows():
        issues = []
        score = 0
        drone_caps = [c.strip().lower() for c in d["capabilities"].split(",")]

        # Capability match
        cap_match = any(nc in drone_caps for nc in needed_caps) if needed_caps else True
        if cap_match:
            score += 3
        else:
            issues.append(f"Missing capabilities: needs {list(needed_caps)}, has {drone_caps}")

        # Weather check
        if weather.lower() == "rainy":
            if "ip43" in d["weather_resistance"].lower():
                score += 3
            else:
                issues.append(f"❌ Not rain-rated ({d['weather_resistance']}), mission forecast: {weather}")
        else:
            score += 3  # non-rainy = any drone works

        # Status check
        if d["status"] == "Available":
            score += 2
        elif d["status"] == "Maintenance":
            issues.append(f"Currently in Maintenance")
        else:
            issues.append(f"Status: {d['status']}")

        # Location check
        if d["location"].lower() == mission_location.lower():
            score += 2
        else:
            issues.append(f"Location mismatch: drone in {d['location']}, mission in {mission_location}")

        candidates.append({
            "drone_id": d["drone_id"],
            "model": d["model"],
            "score": score,
            "issues": issues,
            "fit": "✅ Perfect" if score >= 8 else ("⚠️ Partial" if score >= 5 else "❌ Poor")
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates, f"Found {len(candidates)} drone candidates for {project_id}."


# ─── CONFLICT DETECTION ──────────────────────────────────────────────

def detect_all_conflicts(pilots, drones, missions):
    """Run all conflict checks and return a comprehensive report."""
    conflicts = []

    for _, m in missions.iterrows():
        proj = m["project_id"]
        start = date_parser.parse(m["start_date"])
        end = date_parser.parse(m["end_date"])
        days = (end - start).days + 1
        required_skills = [s.strip() for s in m["required_skills"].split(",")]
        required_certs = [c.strip() for c in m["required_certs"].split(",")]

        # Check assigned pilots
        assigned_pilots = pilots[pilots["current_assignment"] == proj.replace("PRJ", "Project-")]
        # Also check direct match
        assigned_pilots2 = pilots[pilots["current_assignment"] == proj]
        assigned_pilots = pd.concat([assigned_pilots, assigned_pilots2]).drop_duplicates()

        for _, p in assigned_pilots.iterrows():
            # Skill mismatch
            pilot_skills = [s.strip().lower() for s in p["skills"].split(",")]
            for rs in required_skills:
                if rs.lower() not in pilot_skills:
                    conflicts.append(f"🔴 SKILL MISMATCH: {p['name']} assigned to {proj} but lacks '{rs}' skill")

            # Cert mismatch
            pilot_certs = [c.strip().lower() for c in p["certifications"].split(",")]
            for rc in required_certs:
                if rc.lower() not in pilot_certs:
                    conflicts.append(f"🔴 CERT MISMATCH: {p['name']} assigned to {proj} but lacks '{rc}' certification")

            # Location mismatch
            if p["location"].lower() != m["location"].lower():
                conflicts.append(f"🟡 LOCATION MISMATCH: {p['name']} is in {p['location']} but {proj} is in {m['location']}")

            # Budget overrun
            cost = days * p["daily_rate_inr"]
            if cost > m["mission_budget_inr"]:
                conflicts.append(f"🔴 BUDGET OVERRUN: {p['name']} costs ₹{cost} for {proj} (budget: ₹{m['mission_budget_inr']})")

        # Check assigned drones
        assigned_drones = drones[drones["current_assignment"] == proj.replace("PRJ", "Project-")]
        assigned_drones2 = drones[drones["current_assignment"] == proj]
        assigned_drones = pd.concat([assigned_drones, assigned_drones2]).drop_duplicates()

        for _, d in assigned_drones.iterrows():
            # Maintenance check
            if d["status"] == "Maintenance":
                conflicts.append(f"🔴 MAINTENANCE: {d['drone_id']} assigned to {proj} but currently in Maintenance")

            # Weather check
            if m["weather_forecast"].lower() == "rainy" and "ip43" not in d["weather_resistance"].lower():
                conflicts.append(f"🔴 WEATHER RISK: {d['drone_id']} is not rain-rated but {proj} forecast is Rainy")

            # Location mismatch
            if d["location"].lower() != m["location"].lower():
                conflicts.append(f"🟡 LOCATION MISMATCH: {d['drone_id']} is in {d['location']} but {proj} is in {m['location']}")

    # Double-booking detection (pilots)
    for _, p in pilots.iterrows():
        if p["current_assignment"] == "-" or pd.isna(p["current_assignment"]):
            continue
        assignments = [a.strip() for a in str(p["current_assignment"]).split(",")]
        if len(assignments) > 1:
            conflicts.append(f"🔴 DOUBLE-BOOKED: {p['name']} assigned to multiple: {assignments}")

    # Double-booking detection (drones)
    for _, d in drones.iterrows():
        if d["current_assignment"] == "-" or pd.isna(d["current_assignment"]):
            continue
        assignments = [a.strip() for a in str(d["current_assignment"]).split(",")]
        if len(assignments) > 1:
            conflicts.append(f"🔴 DOUBLE-BOOKED: {d['drone_id']} assigned to multiple: {assignments}")

    if not conflicts:
        conflicts.append("✅ No conflicts detected across all missions.")

    return conflicts


# ─── URGENT REASSIGNMENT ────────────────────────────────────────────

def find_urgent_reassignment(pilots, drones, missions, project_id):
    """
    Urgent reassignment: When a pilot/drone becomes unavailable for a mission,
    find the best available replacement considering:
    1. Matching skills/certs
    2. Same location preferred
    3. Within budget
    4. Available immediately
    Returns a reassignment plan.
    """
    mission = missions[missions["project_id"] == project_id]
    if mission.empty:
        return f"Mission {project_id} not found."

    m = mission.iloc[0]
    result = f"🚨 URGENT REASSIGNMENT PLAN for {project_id} ({m['client']}, {m['location']})\n"
    result += f"   Priority: {m['priority']} | Dates: {m['start_date']} to {m['end_date']}\n"
    result += f"   Weather: {m['weather_forecast']} | Budget: ₹{m['mission_budget_inr']}\n\n"

    # Find best pilot
    pilot_candidates, _ = match_pilots_to_mission(pilots, missions, project_id)
    available_pilots = [c for c in pilot_candidates if c["score"] >= 6]

    result += "👨‍✈️ PILOT OPTIONS:\n"
    if available_pilots:
        for i, c in enumerate(available_pilots[:3], 1):
            issues_str = ", ".join(c["issues"]) if c["issues"] else "None"
            result += f"  {i}. {c['name']} ({c['pilot_id']}) - {c['fit']} - Cost: ₹{c['total_cost']} - Issues: {issues_str}\n"
    else:
        result += "  ❌ No suitable pilots available. Consider: extending dates, increasing budget, or cross-location deployment.\n"

    # Find best drone
    drone_candidates, _ = match_drones_to_mission(drones, missions, project_id)
    available_drones = [c for c in drone_candidates if c["score"] >= 5]

    result += "\n🛩️ DRONE OPTIONS:\n"
    if available_drones:
        for i, c in enumerate(available_drones[:3], 1):
            issues_str = ", ".join(c["issues"]) if c["issues"] else "None"
            result += f"  {i}. {c['model']} ({c['drone_id']}) - {c['fit']} - Issues: {issues_str}\n"
    else:
        result += "  ❌ No suitable drones available. Consider: rescheduling or sourcing external drone.\n"

    return result


# ─── DATA SUMMARY ────────────────────────────────────────────────────

def get_full_summary(pilots, drones, missions):
    """Get a text summary of all data for the AI agent context."""
    summary = "=== CURRENT DATA SNAPSHOT ===\n\n"

    summary += "📋 PILOT ROSTER:\n"
    for _, p in pilots.iterrows():
        summary += f"  {p['pilot_id']} | {p['name']} | Skills: {p['skills']} | Certs: {p['certifications']} | "
        summary += f"Location: {p['location']} | Status: {p['status']} | Assignment: {p['current_assignment']} | "
        summary += f"Available: {p['available_from']} | Rate: ₹{p['daily_rate_inr']}/day\n"

    summary += "\n🛩️ DRONE FLEET:\n"
    for _, d in drones.iterrows():
        summary += f"  {d['drone_id']} | {d['model']} | Caps: {d['capabilities']} | Status: {d['status']} | "
        summary += f"Location: {d['location']} | Assignment: {d['current_assignment']} | "
        summary += f"Maintenance Due: {d['maintenance_due']} | Weather: {d['weather_resistance']}\n"

    summary += "\n📌 MISSIONS:\n"
    for _, m in missions.iterrows():
        summary += f"  {m['project_id']} | Client: {m['client']} | Location: {m['location']} | "
        summary += f"Skills: {m['required_skills']} | Certs: {m['required_certs']} | "
        summary += f"Dates: {m['start_date']} to {m['end_date']} | Priority: {m['priority']} | "
        summary += f"Budget: ₹{m['mission_budget_inr']} | Weather: {m['weather_forecast']}\n"

    return summary


def assign_pilot_to_mission(pilots, pilot_id, project_id, missions):
    """Assign a pilot to a mission. Updates status and current_assignment."""
    pidx = pilots.index[pilots["pilot_id"] == pilot_id]
    if pidx.empty:
        return pilots, f"Pilot {pilot_id} not found."
    
    mission = missions[missions["project_id"] == project_id]
    if mission.empty:
        return pilots, f"Mission {project_id} not found."
    
    pilots.loc[pidx, "status"] = "Assigned"
    pilots.loc[pidx, "current_assignment"] = project_id
    name = pilots.loc[pidx, "name"].values[0]
    return pilots, f"✅ {name} ({pilot_id}) assigned to {project_id}."


def assign_drone_to_mission(drones, drone_id, project_id, missions):
    """Assign a drone to a mission. Updates status and current_assignment."""
    didx = drones.index[drones["drone_id"] == drone_id]
    if didx.empty:
        return drones, f"Drone {drone_id} not found."
    
    mission = missions[missions["project_id"] == project_id]
    if mission.empty:
        return drones, f"Mission {project_id} not found."
    
    drones.loc[didx, "status"] = "Assigned"
    drones.loc[didx, "current_assignment"] = project_id
    model = drones.loc[didx, "model"].values[0]
    return drones, f"✅ {drone_id} ({model}) assigned to {project_id}."
