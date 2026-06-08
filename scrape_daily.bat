@echo off
REM Run BCV scraper - call this via Windows Task Scheduler daily
cd /d "%~dp0"
C:\Windows\py.exe scraper.py
