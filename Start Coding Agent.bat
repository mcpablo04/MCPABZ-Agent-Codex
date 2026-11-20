@echo off
cd /d "%~dp0"
python CodingAgent.py
if errorlevel 1 pause
