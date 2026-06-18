import gspread

gc = gspread.service_account(filename="credentials.json")

sheet_id = "1qUxP1TQDTOn1jXn4k3UELgvueBABeo5pzzkLSClTHvc"

spreadsheet = gc.open_by_key(sheet_id)

worksheet = spreadsheet.sheet1

data = worksheet.get_all_records()

print(data)