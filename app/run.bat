@echo off
REM Sakala AI POC - start the server and open the app
cd /d "%~dp0"
if not exist data\sakala.db (
  echo First run: building the database from "Sample grievance cases.xlsx" and training the local model ^(about 2 minutes^)...
  python -m server.ingest
)
start "" http://localhost:8020
python -m uvicorn server.api:app --port 8020
