@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_one_click_start.ps1" -Profile safe
if errorlevel 1 pause
