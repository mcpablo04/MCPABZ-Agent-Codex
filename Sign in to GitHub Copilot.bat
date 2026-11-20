@echo off
cd /d "%~dp0"
echo GitHub Copilot sign-in: type /login, then follow the browser prompts.
call "%~dp0copilot_cli\node_modules\.bin\copilot.cmd"
pause
