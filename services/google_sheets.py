import gspread


def extract_sheet_id(sheet_url):
    return sheet_url.split("/d/")[1].split("/")[0]


def get_sheet_data(sheet_url):
    gc = gspread.service_account(filename="credentials.json")

    sheet_id = extract_sheet_id(sheet_url)

    spreadsheet = gc.open_by_key(sheet_id)

    worksheet = spreadsheet.sheet1

    return worksheet.get_all_records()