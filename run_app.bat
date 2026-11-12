@echo off
cd /d "%~dp0"
echo Starting YOLOv8 PPE Detection & Auto-Labeling Pipeline (Port 8070)...
python -X utf8 server.py
pause

