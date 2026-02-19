"""
Skylark Drones - Google Sheets Integration
2-way sync: Read all data, Write pilot/drone status updates back.
Uses a service account for authentication.
"""
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_gspread_client():
    """Authenticate and return a gspread client using service account from Streamlit secrets."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(dict(creds_dict), scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.warning(f"Google Sheets connection not configured: {e}")
        return None


def read_sheet_to_df(client, spreadsheet_id, sheet_name):
    """Read a Google Sheet tab into a pandas DataFrame."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return None


def write_df_to_sheet(client, spreadsheet_id, sheet_name, df):
    """Write a full DataFrame back to a Google Sheet tab (overwrite)."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        # Write header + data
        header = df.columns.tolist()
        rows = df.astype(str).values.tolist()
        worksheet.update([header] + rows)
        return True, "✅ Synced to Google Sheets."
    except Exception as e:
        return False, f"❌ Sheets sync failed: {e}"


def sync_pilot_status(client, spreadsheet_id, pilot_id, new_status, current_assignment=None):
    """Update a single pilot's status in Google Sheets."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet("pilot_roster")
        cell = worksheet.find(pilot_id)
        if cell is None:
            return False, f"Pilot {pilot_id} not found in sheet."

        row = cell.row
        # Status is column 6, current_assignment is column 7
        worksheet.update_cell(row, 6, new_status)
        if current_assignment is not None:
            worksheet.update_cell(row, 7, current_assignment)
        return True, f"✅ {pilot_id} status synced to Google Sheets."
    except Exception as e:
        return False, f"❌ Sync failed: {e}"


def sync_drone_status(client, spreadsheet_id, drone_id, new_status, current_assignment=None):
    """Update a single drone's status in Google Sheets."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet("drone_fleet")
        cell = worksheet.find(drone_id)
        if cell is None:
            return False, f"Drone {drone_id} not found in sheet."

        row = cell.row
        # Status is column 4, current_assignment is column 6
        worksheet.update_cell(row, 4, new_status)
        if current_assignment is not None:
            worksheet.update_cell(row, 6, current_assignment)
        return True, f"✅ {drone_id} status synced to Google Sheets."
    except Exception as e:
        return False, f"❌ Sync failed: {e}"


def load_data_from_sheets(client, spreadsheet_id):
    """Load all three datasets from Google Sheets. Falls back to CSV if sheets unavailable."""
    pilots = read_sheet_to_df(client, spreadsheet_id, "pilot_roster")
    drones = read_sheet_to_df(client, spreadsheet_id, "drone_fleet")
    missions = read_sheet_to_df(client, spreadsheet_id, "missions")
    return pilots, drones, missions


def full_sync_to_sheets(client, spreadsheet_id, pilots, drones, missions):
    """Sync all DataFrames back to Google Sheets."""
    results = []
    ok1, msg1 = write_df_to_sheet(client, spreadsheet_id, "pilot_roster", pilots)
    results.append(msg1)
    ok2, msg2 = write_df_to_sheet(client, spreadsheet_id, "drone_fleet", drones)
    results.append(msg2)
    ok3, msg3 = write_df_to_sheet(client, spreadsheet_id, "missions", missions)
    results.append(msg3)
    return results
