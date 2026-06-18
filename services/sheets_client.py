import gspread
from services.google_auth import get_google_client
from services.worksheet_reader import discover_worksheets


def validate_sheet_url(url: str) -> bool:
    """Validate if the string is a google spreadsheets URL."""
    return "docs.google.com/spreadsheets" in url


def get_spreadsheet(sheet_url: str) -> gspread.Spreadsheet:
    """Retrieve the spreadsheet using authorized client with error handling."""
    if not validate_sheet_url(sheet_url):
        raise ValueError("Invalid Google Sheets URL format.")
    client = get_google_client()
    try:
        return client.open_by_url(sheet_url)
    except Exception as e:
        raise RuntimeError(f"Failed to open spreadsheet by URL: {str(e)}")


def get_spreadsheet_data(sheet_url: str) -> dict:
    """Fetch all worksheet names and details from the spreadsheet URL."""
    spreadsheet = get_spreadsheet(sheet_url)
    worksheets = discover_worksheets(spreadsheet)
    return {
        "spreadsheet_name": spreadsheet.title,
        "worksheets": worksheets,
        "spreadsheet": spreadsheet
    }
