
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# ------------------- Google Sheets Setup -------------------
creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(creds)
sheet = gc.open_by_url(
    "https://docs.google.com/spreadsheets/d/19xtFu9__d6FSny_PP_1AFINLCDfYoKaX9TIOmYVsmTs/edit"
)
worksheet = sheet.sheet1

def get_data():
    data = worksheet.get_all_values()
    # Skip first row and select first 3 columns
    df = pd.DataFrame(data[1:], columns=["timestamp", "uptime", "value", "sfdsa", "asdf"]).iloc[:, :3]

    # Expand rows and pick value closest to mean
    rows = []
    for n, row in df.iterrows():
        try:
            values = [v for v in row["value"].split(":") if v != '']
            values_np = np.array(values, dtype=int)
            suitable_value = values_np[np.abs(values_np - values_np.mean()).argmin()]
            rows.append({
                "timestamp": row["timestamp"],
                "value": int(suitable_value)
            })
        except:
            print(f"Skipping invalid in row {n}")

    expanded_df = pd.DataFrame(rows)
    expanded_df["timestamp"] = pd.to_datetime(expanded_df["timestamp"])
    return expanded_df
