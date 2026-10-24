@echo off
setlocal
cd /d "%~dp0"
python tools\build_host.py > buildlog.txt 2>&1
set RESULT=%ERRORLEVEL%
type buildlog.txt
if not "%RESULT%"=="0" exit /b %RESULT%
echo GBA ROM: build\sample.gba
exit /b 0
