# Decision Log — SkyOps AI (Drone Operations Coordinator)

## Key Assumptions

1. **Pilot "available_from" date**: Interpreted as the date a pilot becomes free — used to check if an on-leave pilot will be available before a mission starts.
2. **Project naming**: Missions use `PRJ001` format while sample assignments use `Project-A` — the system handles both naming conventions when checking conflicts.
3. **Weather compatibility**: "Rainy" weather requires IP43-rated drones. All other forecasts (Sunny, Cloudy) are safe for any drone.
4. **Skill-to-capability mapping**: Mapping/Survey missions need LiDAR or RGB drones; Thermal missions need Thermal drones; Inspection needs RGB.
5. **Budget = total mission budget**: Compared against `daily_rate × days` for the full mission duration (inclusive of start and end dates).
6. **Single assignment model**: A pilot/drone can only be assigned to one mission at a time. Multiple assignments = double-booking conflict.

## Trade-offs Chosen

| Decision | Alternative | Why |
|----------|------------|-----|
| **Groq (LLaMA 3.3 70B)** as AI backbone | Google Gemini, OpenAI GPT-4, Claude API | Initially built with Gemini 2.0 Flash, but encountered persistent free-tier quota issues (limit: 0) across multiple Google Cloud projects. Switched to Groq which offers a generous free tier with LLaMA 3.3 70B — fast inference, no credit card required, and reliable API access. This decision prioritized **reliability for evaluators** over model brand. |
| **Streamlit** for UI | React + FastAPI, Gradio | Fastest to build, deploy, and test. Built-in chat UI, data tables, and Streamlit Cloud for free hosting |
| **Session state + CSV fallback** | Database (SQLite/Postgres) | For a demo with 4 pilots/4 drones/3 missions, in-memory state is sufficient. CSV fallback means the app works even without Sheets configured |
| **Action blocks in AI responses** | Dedicated function calling API | Simpler to implement, more transparent to the user (they see what action is being taken), and easier to debug |
| **Scored matching system** | Binary yes/no matching | Scoring (0-12 for pilots, 0-10 for drones) lets us rank candidates and show partial matches — more useful for real coordination |
| **Proactive conflict detection** | On-demand only | Conflicts are checked both on-demand AND automatically after every assignment — prevents silent errors |

## Interpretation: "Urgent Reassignments"

**My interpretation:** When a pilot or drone suddenly becomes unavailable (e.g., goes on leave, equipment failure, maintenance) for an assigned or upcoming mission, the coordinator needs to immediately find the best replacement. 

**Implementation:** The `find_urgent_reassignment` function:
1. Takes a mission (project_id) that needs reassignment
2. Runs the full matching algorithm against ALL available pilots and drones
3. Scores and ranks candidates, showing top 3 options with trade-offs
4. Flags if no suitable replacement exists and suggests alternatives (extend dates, increase budget, cross-location deployment)
5. Works through both the AI chat ("find urgent reassignment for PRJ002") and the Missions tab UI

This covers the realistic scenario where a coordinator gets a call that someone can't make it and needs to scramble a replacement within minutes.

## What I'd Do Differently With More Time

1. **Native function calling**: Use Groq's tool/function calling API instead of parsing action blocks from text — more reliable and structured.
2. **Multi-step assignment workflow**: Add confirmation dialogs, pre-flight conflict checks before executing, and rollback capability.
3. **Notification system**: Email/Slack alerts when conflicts are detected or urgent reassignments are needed.
4. **Historical tracking**: Log all changes with timestamps for audit trails and analytics (e.g., "how often does P002 get reassigned?").
5. **Map visualization**: Show pilot and drone locations on a map, mission sites, and travel distances for location mismatch resolution.
6. **More sophisticated matching**: Factor in pilot experience history, client preferences, travel time/cost, and drone battery/range limitations.
7. **Automated scheduling**: Given all missions and resources, compute an optimal global assignment plan (constraint satisfaction problem).
8. **Testing**: Unit tests for all data_engine functions, integration tests for the Sheets sync, and end-to-end tests for the AI agent.
