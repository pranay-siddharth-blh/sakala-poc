"""Central settings for the Sakala AI POC."""
from pathlib import Path
from datetime import datetime

APP = Path(__file__).resolve().parents[1]           # D:\Sakala POC\app
PROJECT = APP.parent                                 # D:\Sakala POC
DATA = APP / "data"
DB_PATH = DATA / "sakala.db"
WEB = APP / "web"
SOURCE_XLSX = PROJECT / "Sample grievance cases.xlsx"   # 9,999 real iPGRS grievances, 3–9 Oct 2026


PILOT_DISTRICT = "Mysuru"
PILOT_TALUKS = ["Piriyapatna", "Hunsur", "Mysuru"]
PILOT_DEPTS = {
    "REV": "Revenue Department",
    "RDPR": "Rural Development and Panchayath Raj Department",
    "FOOD": "Food and Civil Supplies Department",
}

# ASSUMED grievance timelines per level (iPGRS does not publish them). Sakala services use their legal timeline.
SLA_DAYS = {"L1": 7, "L2": 5, "L3": 3}
DEMO_START = datetime(2026, 10, 14, 10, 0, 0)        # pilot go-live on the demo clock

# Sakala Act 2011: s.9 compensation ₹20/day capped at ₹500; s.13 appeals 30 / 60 days.
COMP_PER_DAY, COMP_CAP = 20, 500
