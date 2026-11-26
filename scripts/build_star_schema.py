"""
Call Center Operations & SLA Analytics
Step 1-2: Data cleaning, feature derivation, and star-schema export.

Input : /mnt/user-data/uploads/8e4113bf-Call-Center-Dataset.xlsx
Output: /home/claude/work/output/{fact_calls.csv, dim_agents.csv, dim_topics.csv,
        clean_calls_flat.csv, kpi_summary.csv}
"""
import pandas as pd
import numpy as np

SRC = "/mnt/user-data/uploads/8e4113bf-Call-Center-Dataset.xlsx"
OUT = "/home/claude/work/output"

# ---------------------------------------------------------------
# 1. LOAD + CLEAN
# ---------------------------------------------------------------
df = pd.read_excel(SRC, sheet_name="Sheet1")

# 1a. Drop the empty/junk trailing columns
junk_cols = [c for c in ["Unnamed: 10", "Unnamed: 11", "Unnamed: 12"] if c in df.columns]
df = df.drop(columns=junk_cols)

# 1b. Validate: every null in Speed/AvgTalkDuration/Satisfaction belongs to an
#     unanswered call (Answered == 'N'), i.e. these are abandoned calls, not
#     data-entry errors.
null_mask = df["Speed of answer in seconds"].isnull()
assert null_mask.sum() == 946, f"Expected 946 null rows, found {null_mask.sum()}"
assert (df.loc[null_mask, "Answered (Y/N)"] == "N").all(), "Found nulls on an answered call"
assert (df.loc[~null_mask, "Answered (Y/N)"] == "Y").all(), "Found an unanswered call with data"
assert (df.loc[null_mask, "Resolved"] == "N").all(), "Abandoned call marked Resolved=Y"

# 1c. Parse Date (string) -> real date
df["Date"] = pd.to_datetime(df["Date"]).dt.date

# 1d. AvgTalkDuration (datetime.time, HH:MM:SS) -> talk_duration_sec (float, NaN for abandoned)
def time_to_seconds(t):
    if pd.isnull(t):
        return np.nan
    return t.hour * 3600 + t.minute * 60 + t.second

df["talk_duration_sec"] = df["AvgTalkDuration"].apply(time_to_seconds)

# 1e. Derive day_of_week and hour_of_day
df["day_of_week"] = pd.to_datetime(df["Date"]).dt.day_name()
df["hour_of_day"] = df["Time"].apply(lambda t: t.hour)

# Rename the raw SLA/speed column for a consistent snake_case name downstream
df = df.rename(columns={"Speed of answer in seconds": "speed_of_answer_sec"})

# Save the full cleaned flat table too (handy for the "data cleaning" portfolio artifact)
flat = df.rename(columns={
    "Call Id": "call_id",
    "Agent": "agent_name",
    "Topic": "topic_name",
    "Answered (Y/N)": "answered",
    "Resolved": "resolved",
    "Satisfaction rating": "satisfaction_rating",
})[[
    "call_id", "agent_name", "Date", "Time", "day_of_week", "hour_of_day",
    "topic_name", "answered", "resolved", "speed_of_answer_sec",
    "talk_duration_sec", "satisfaction_rating"
]]
flat.to_csv(f"{OUT}/clean_calls_flat.csv", index=False)

print("1) Cleaning complete.")
print(f"   Rows: {len(df)}  |  Abandoned (Answered=N): {null_mask.sum()}  |  Dropped cols: {junk_cols}")

# ---------------------------------------------------------------
# 2. STAR SCHEMA
# ---------------------------------------------------------------

# ---- dim_agents ----
agent_names = sorted(df["Agent"].unique())
# The raw timestamps don't actually encode a real shift pattern (every agent is
# active ~09:00-18:00), so shifts are assigned as a realistic scenario split:
# half the roster on an early/Morning shift, half on a later/Afternoon shift.
morning_agents = {"Becky", "Diane", "Greg", "Martha"}
dim_agents = pd.DataFrame({
    "Agent_Id": [f"A{str(i+1).zfill(3)}" for i in range(len(agent_names))],
    "Agent_Name": agent_names,
    "Team_Shift": ["Morning" if a in morning_agents else "Afternoon" for a in agent_names],
})
dim_agents.to_csv(f"{OUT}/dim_agents.csv", index=False)

# ---- dim_topics ----
# SLA targets set per realistic BPO/call-center practice: simple/transactional
# topics get tighter targets, complex topics get more generous ones.
sla_targets = {
    "Payment related": 45,
    "Streaming": 40,
    "Admin Support": 50,
    "Technical Support": 60,
    "Contract related": 75,
}
topic_names = sorted(df["Topic"].unique(), key=lambda t: list(sla_targets).index(t))
dim_topics = pd.DataFrame({
    "Topic_Id": [f"T{str(i+1).zfill(2)}" for i in range(len(topic_names))],
    "Topic_Name": topic_names,
    "SLA_Target_Sec": [sla_targets[t] for t in topic_names],
})
dim_topics.to_csv(f"{OUT}/dim_topics.csv", index=False)

# ---- fact_calls ----
agent_map = dict(zip(dim_agents["Agent_Name"], dim_agents["Agent_Id"]))
topic_map = dict(zip(dim_topics["Topic_Name"], dim_topics["Topic_Id"]))

fact_calls = pd.DataFrame({
    "Call_Id": df["Call Id"],
    "Agent_Id": df["Agent"].map(agent_map),
    "Topic_Id": df["Topic"].map(topic_map),
    "Date": df["Date"],
    "Time": df["Time"].apply(lambda t: t.strftime("%H:%M:%S")),
    "Day_Of_Week": df["day_of_week"],
    "Hour_Of_Day": df["hour_of_day"],
    "Answered": df["Answered (Y/N)"],
    "Resolved": df["Resolved"],
    "Speed_Of_Answer_Sec": df["speed_of_answer_sec"],
    "Talk_Duration_Sec": df["talk_duration_sec"],
    "Satisfaction_Rating": df["Satisfaction rating"],
})
fact_calls.to_csv(f"{OUT}/fact_calls.csv", index=False)

print("2) Star schema exported: fact_calls.csv, dim_agents.csv, dim_topics.csv")
print(dim_agents.to_string(index=False))
print(dim_topics.to_string(index=False))

# ---------------------------------------------------------------
# 3. KPI SUMMARY
# ---------------------------------------------------------------
total_calls = len(df)
answered = (df["Answered (Y/N)"] == "Y").sum()
abandoned = (df["Answered (Y/N)"] == "N").sum()
answer_rate = answered / total_calls
abandon_rate = abandoned / total_calls

answered_df = df[df["Answered (Y/N)"] == "Y"]
asa = answered_df["speed_of_answer_sec"].mean()
aht = answered_df["talk_duration_sec"].mean()
resolved_among_answered = (answered_df["Resolved"] == "Y").sum()
fcr_rate = resolved_among_answered / answered
avg_csat = answered_df["Satisfaction rating"].mean()

def fmt_mmss(seconds):
    m, s = divmod(round(seconds), 60)
    return f"{m}:{s:02d}"

kpi_rows = [
    ("Toplam Çağrı (Total Calls)", f"{total_calls:,}"),
    ("Cevaplanan Çağrı (Answered Calls)", f"{answered:,}"),
    ("Cevaplanma Oranı (Answer Rate)", f"{answer_rate:.2%}"),
    ("Kaçan Çağrı (Abandoned Calls)", f"{abandoned:,}"),
    ("Abandon Rate (Terk Oranı)", f"{abandon_rate:.2%}"),
    ("Ortalama Yanıtlama Hızı - ASA (sn)", f"{asa:.2f}"),
    ("Ortalama Konuşma Süresi - AHT (sn)", f"{aht:.2f}"),
    ("Ortalama Konuşma Süresi - AHT (mm:ss)", fmt_mmss(aht)),
    ("Çözüm Oranı - FCR % (cevaplananlar içinde)", f"{fcr_rate:.2%}"),
    ("Ortalama CSAT (1-5)", f"{avg_csat:.2f}"),
]
kpi_df = pd.DataFrame(kpi_rows, columns=["KPI", "Değer"])
kpi_df.to_csv(f"{OUT}/kpi_summary.csv", index=False)

print("\n3) KPI summary:")
print(kpi_df.to_string(index=False))

# Save raw numeric values too, for the Excel builder step
raw_kpis = {
    "total_calls": total_calls,
    "answered": int(answered),
    "abandoned": int(abandoned),
    "answer_rate": answer_rate,
    "abandon_rate": abandon_rate,
    "asa_sec": asa,
    "aht_sec": aht,
    "fcr_rate": fcr_rate,
    "avg_csat": avg_csat,
}
import json
with open(f"{OUT}/raw_kpis.json", "w") as f:
    json.dump(raw_kpis, f, indent=2)
