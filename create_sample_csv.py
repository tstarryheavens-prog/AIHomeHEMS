import pandas as pd
import numpy as np

# Create sample CSV data for 2016-2026
dates = pd.date_range(start="2016-01-01 00:00", end="2026-06-30 23:00", freq="1h")
np.random.seed(42)
# Load in kWh per hour: between 0.2 and 1.5 kWh
kwh = np.round(np.random.uniform(0.2, 1.4, size=len(dates)), 2)

df_sample = pd.DataFrame({
    "日時": dates.strftime("%Y/%m/%d %H:%M"),
    "使用量(kWh)": kwh
})

df_sample.to_csv("sample_katene_2016_2026.csv", index=False, encoding="shift_jis")
print(f"Sample Katene CSV generated: {len(df_sample)} rows!")
