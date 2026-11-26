"""
Build the Excel KPI discovery-summary workbook (English).
Formula-driven: every KPI is computed live from the Data sheet, not hardcoded.
"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT_DIR = "/home/claude/work/output"
flat = pd.read_csv(f"{OUT_DIR}/clean_calls_flat.csv")

wb = Workbook()

# ------------------------------------------------------------------
# Sheet 1: Data  (the cleaned flat table the KPI formulas reference)
# ------------------------------------------------------------------
ws_data = wb.active
ws_data.title = "Data"

headers = ["call_id", "agent_name", "date", "time", "day_of_week", "hour_of_day",
           "topic_name", "answered", "resolved", "speed_of_answer_sec",
           "talk_duration_sec", "satisfaction_rating"]
header_font = Font(name="Arial", bold=True, color="FFFFFF")
header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")

for col_idx, h in enumerate(headers, start=1):
    c = ws_data.cell(row=1, column=col_idx, value=h)
    c.font = header_font
    c.fill = header_fill
    c.alignment = Alignment(horizontal="center")

n_rows = len(flat)
for r, row in enumerate(flat.itertuples(index=False), start=2):
    for c_idx, val in enumerate(row, start=1):
        cell = ws_data.cell(row=r, column=c_idx, value=(None if pd.isna(val) else val))
        cell.font = Font(name="Arial", size=10)

for col_idx, h in enumerate(headers, start=1):
    ws_data.column_dimensions[get_column_letter(col_idx)].width = max(12, len(h) + 2)
ws_data.freeze_panes = "A2"

last_row = n_rows + 1  # data occupies rows 2..last_row

# Column letters, for building formulas clearly
COL = {h: get_column_letter(i + 1) for i, h in enumerate(headers)}

# ------------------------------------------------------------------
# Sheet 2: KPI Summary
# ------------------------------------------------------------------
ws = wb.create_sheet("KPI Summary")
ws.sheet_view.showGridLines = False

title_font = Font(name="Arial", bold=True, size=14, color="1F3864")
sub_font = Font(name="Arial", italic=True, size=10, color="595959")
ws["B2"] = "Call Center Operations & SLA Analytics"
ws["B2"].font = title_font
ws["B3"] = "Core KPI Summary  |  Period: 2021-01-01 to 2021-03-31  |  Source: Call-Center-Dataset.xlsx (5,000 calls)"
ws["B3"].font = sub_font

hdr_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
hdr_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
thin = Side(style="thin", color="B7B7B7")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
label_font = Font(name="Arial", size=11)
value_font = Font(name="Arial", bold=True, size=11, color="1F3864")

ws["B5"] = "KPI"
ws["C5"] = "Value"
for col in ("B5", "C5"):
    ws[col].font = hdr_font
    ws[col].fill = hdr_fill
    ws[col].alignment = Alignment(horizontal="center")
    ws[col].border = border

H, I, J, K, L = COL["answered"], COL["resolved"], COL["speed_of_answer_sec"], COL["talk_duration_sec"], COL["satisfaction_rating"]
CID = COL["call_id"]

rows = [
    ("Total Calls",
     f"=COUNTA(Data!{CID}2:{CID}{last_row})", "#,##0"),
    ("Answered Calls",
     f'=COUNTIF(Data!{H}2:{H}{last_row},"Y")', "#,##0"),
    ("Answer Rate",
     f"=C7/C6", "0.00%"),
    ("Abandoned Calls (Answered = N)",
     f'=COUNTIF(Data!{H}2:{H}{last_row},"N")', "#,##0"),
    ("Abandon Rate",
     f"=C9/C6", "0.00%"),
    ("Average Speed of Answer - ASA (sec)",
     f'=AVERAGEIF(Data!{H}2:{H}{last_row},"Y",Data!{J}2:{J}{last_row})', "0.00"),
    ("Average Handle Time - AHT (sec)",
     f'=AVERAGEIF(Data!{H}2:{H}{last_row},"Y",Data!{K}2:{K}{last_row})', "0.00"),
    ("Average Handle Time - AHT (mm:ss)",
     f'=TEXT(INT(C12/60),"0")&":"&TEXT(MOD(C12,60),"00")', "@"),
    ("First Call Resolution - FCR % (of answered calls)",
     f'=COUNTIFS(Data!{H}2:{H}{last_row},"Y",Data!{I}2:{I}{last_row},"Y")/C7', "0.00%"),
    ("Average CSAT (1-5)",
     f'=AVERAGEIF(Data!{H}2:{H}{last_row},"Y",Data!{L}2:{L}{last_row})', "0.00"),
]

r = 6
for label, formula, numfmt in rows:
    ws.cell(row=r, column=2, value=label).font = label_font
    ws.cell(row=r, column=2).border = border
    vc = ws.cell(row=r, column=3, value=formula)
    vc.font = value_font
    vc.border = border
    vc.number_format = numfmt
    vc.alignment = Alignment(horizontal="center")
    r += 1

ws.column_dimensions["A"].width = 3
ws.column_dimensions["B"].width = 48
ws.column_dimensions["C"].width = 16

note_font = Font(name="Arial", italic=True, size=9, color="808080")
ws.cell(row=r + 1, column=2,
        value="Note: ASA, AHT and CSAT are computed only over answered calls (Answered = Y); "
              "these fields are blank in the source data for abandoned calls.").font = note_font
ws.cell(row=r + 2, column=2,
        value="FCR is the share of Resolved = Y among answered calls.").font = note_font

wb.save(f"{OUT_DIR}/call_center_kpi_summary.xlsx")
print("Saved call_center_kpi_summary.xlsx")
