@echo off
setlocal EnableExtensions
set PORT=9282
for /f "tokens=1,2 delims==" %%A in ('type "%~dp0..\..\..\.env.docker" 2^>nul ^| findstr /b "APP_HTTP_PORT="') do set PORT=%%B
start "" "http://127.0.0.1:%PORT%"
