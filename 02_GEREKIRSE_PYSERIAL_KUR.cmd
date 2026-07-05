@echo off
setlocal EnableExtensions
title GT ELEKTRONIK - PySerial Kur
echo.
echo PySerial kuruluyor...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m pip install pyserial
    pause
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    python -m pip install pyserial
    pause
    exit /b
)

echo HATA: Python bulunamadi.
pause
