@echo off
setlocal EnableExtensions
title GT ELEKTRONIK v030 Paradise Full Panel
cd /d "%~dp0PROGRAM"

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -V >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo HATA: Python bulunamadi.
    echo PC kalibrasyon programi icin Python 3 gerekir.
    echo UF2 cihazlari Python olmadan da oyun icinde calisir.
    pause
    exit /b 1
)

%PYTHON_CMD% "gt_v030_paradise_pc_cal_test.py"
pause
endlocal
