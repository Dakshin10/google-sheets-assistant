from services.google_sheets import get_sheet_data
from services.schema_detector import generate_create_table_sql
from services.sql_generator import generate_insert_sql

import pandas as pd

sheet_url = input("Enter Google Sheet URL: ")

data = get_sheet_data(sheet_url)

df = pd.DataFrame(data)

create_sql = generate_create_table_sql(df, "products")

print("\nCREATE TABLE:\n")
print(create_sql)

insert_sqls = generate_insert_sql(df, "products")

print("\nINSERTS:\n")

for sql in insert_sqls:
    print(sql)