"""
Google Sheets integration for uploading attention report data.
"""
from __future__ import annotations

import os
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .analysis import AggregatedRow

# Spreadsheet ID extracted from the URL
SPREADSHEET_ID = "1acQTFG3yyarLCwPDeZTqOPx_W9JcNg39nC8BCu-msvQ"

# Path to credentials file (Service Account JSON)
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_MODULE_DIR)
CREDENTIALS_FILE = os.path.join(_PROJECT_DIR, "credentials.json")


def upload_to_gsheet(rows: List['AggregatedRow']) -> bool:
    """
    Upload the report data to Google Sheets.
    Clears the entire sheet and writes fresh data.
    Uses the same sorting and formatting as output.py.
    
    Returns True on success, False on failure.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Error: gspread or google-auth not installed. Run: pip install gspread google-auth")
        return False
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: Credentials file not found at {CREDENTIALS_FILE}")
        print("Please download the service account JSON from Google Cloud Console.")
        return False
    
    try:
        # Use output.build_rows for consistent sorting and formatting
        from . import output
        
        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Authenticate
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open spreadsheet
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1  # First sheet (gid=0)
        
        # Clear entire sheet
        worksheet.clear()
        
        # Prepare header (same as output.COLUMNS)
        headers = list(output.COLUMNS)
        
        # Build data rows using the same function as CSV output
        # Use for_excel=False since Google Sheets handles codes properly
        data_rows = output.build_rows(rows, "-", for_excel=False)
        
        # Combine header and data
        all_data = [headers] + data_rows
        
        # Write all data at once
        if all_data:
            worksheet.update(range_name='A1', values=all_data)
        
        print(f"Successfully uploaded {len(data_rows)} rows to Google Sheets.")
        return True
        
    except Exception as e:
        print(f"Error uploading to Google Sheets: {e}")
        return False

