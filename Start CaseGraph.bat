@echo off
cd /d C:\Users\aksha\Downloads\casegraph

set "DATABASE_URL=postgresql://postgres:Ak%%40160606@localhost:5432/casegraph"

echo Starting CaseGraph...
python app.py

pause