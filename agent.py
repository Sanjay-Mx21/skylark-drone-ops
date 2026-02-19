"""
Skylark Drones - AI Agent
Uses Google Gemini to provide a conversational interface for drone operations coordination.
Interprets user queries, calls appropriate data_engine functions, and returns natural language responses.
"""
import google.generativeai as genai
import json
import re
from data_engine import (
    query_pilots, calculate_pilot_cost, update_pilot_status, get_current_assignments,
    query_drones, flag_maintenance_issues, update_drone_status,
    match_pilots_to_mission, match_drones_to_mission,
    detect_all_conflicts, find_urgent_reassignment, get_full_summary,
    assign_pilot_to_mission, assign_drone_to_mission,
)

SYSTEM_PROMPT = """You are SkyOps AI, the Drone Operations Coordinator for Skylark Drones. 
You help manage pilot rosters, drone fleets, mission assignments, and detect conflicts.

You have access to live data that is provided to you in each message. Use it to answer accurately.

Your capabilities:
1. **Roster Management**: Query pilots by skill/cert/location/status, calculate costs, update status, view assignments
2. **Assignment Tracking**: Match pilots & drones to missions, assign them, handle reassignments
3. **Drone Inventory**: Query fleet, check weather compatibility, flag maintenance, update status
4. **Conflict Detection**: Double-booking, skill mismatches, location mismatches, budget overruns, weather risks
5. **Urgent Reassignment**: When someone/something becomes unavailable, find best replacement fast

When the user asks to DO something (update status, assign, etc.), respond with a JSON action block so the app can execute it:
```action
{"function": "function_name", "args": {"arg1": "val1", "arg2": "val2"}}
```

Available actions:
- update_pilot_status: args = pilot_id, new_status (Available/Assigned/On Leave/Unavailable)
- update_drone_status: args = drone_id, new_status (Available/Assigned/Maintenance)
- assign_pilot_to_mission: args = pilot_id, project_id
- assign_drone_to_mission: args = drone_id, project_id
- run_conflict_check: no args needed
- find_reassignment: args = project_id

Rules:
- Always use actual data provided. Never make up data.
- When matching, explain WHY a candidate is good or bad.
- Flag any conflicts or risks proactively.
- For cost calculations, show the math: rate × days = total.
- Be concise but thorough. Use tables/bullet points for clarity.
- If an action would cause a conflict, WARN the user before proceeding.
- When you give an action block, also explain what you're doing in natural language.
"""


def get_agent_response(api_key, user_message, data_context, chat_history=None):
    """Get a response from the Gemini AI agent."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )

        # Build conversation with data context
        full_prompt = f"""
CURRENT LIVE DATA:
{data_context}

USER MESSAGE: {user_message}

Respond helpfully. If the user wants to take an action, include the action JSON block.
"""
        # Use chat history if available
        if chat_history:
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(full_prompt)
        else:
            response = model.generate_content(full_prompt)

        return response.text

    except Exception as e:
        return f"❌ AI Error: {str(e)}. Please check your Gemini API key."


def parse_action(response_text):
    """Extract action JSON from AI response if present."""
    pattern = r"```action\s*\n(.*?)\n```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        try:
            action = json.loads(match.group(1).strip())
            return action
        except json.JSONDecodeError:
            return None
    return None


def execute_action(action, pilots, drones, missions):
    """Execute an action parsed from the AI response. Returns updated dataframes and message."""
    func = action.get("function")
    args = action.get("args", {})

    if func == "update_pilot_status":
        pilots, msg = update_pilot_status(pilots, args["pilot_id"], args["new_status"])
        return pilots, drones, missions, msg, "pilot"

    elif func == "update_drone_status":
        drones, msg = update_drone_status(drones, args["drone_id"], args["new_status"])
        return pilots, drones, missions, msg, "drone"

    elif func == "assign_pilot_to_mission":
        pilots, msg = assign_pilot_to_mission(pilots, args["pilot_id"], args["project_id"], missions)
        return pilots, drones, missions, msg, "pilot"

    elif func == "assign_drone_to_mission":
        drones, msg = assign_drone_to_mission(drones, args["drone_id"], args["project_id"], missions)
        return pilots, drones, missions, msg, "drone"

    elif func == "run_conflict_check":
        conflicts = detect_all_conflicts(pilots, drones, missions)
        return pilots, drones, missions, "\n".join(conflicts), None

    elif func == "find_reassignment":
        result = find_urgent_reassignment(pilots, drones, missions, args["project_id"])
        return pilots, drones, missions, result, None

    return pilots, drones, missions, "Unknown action.", None
