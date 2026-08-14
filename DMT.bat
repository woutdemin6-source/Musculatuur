@echo off
setlocal
title DMT - De Musculatuur Tool

rem Deze regel zorgt dat de tool altijd zichzelf terugvindt, ongeacht waar
rem deze map staat (Bureaublad, Documenten, USB-stick, ...) - dus NIET
rem hardcoded naar 1 vaste locatie zoals de vorige versie.
cd /d "%~dp0"

if not exist "app.py" (
    echo Kan app.py niet vinden in deze map:
    echo   %cd%
    echo Zorg dat DMT.bat in dezelfde map staat als app.py, core.py en requirements.txt.
    pause
    exit /b 1
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PY=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "PY=py"
    ) else (
        echo Python is niet gevonden op deze computer.
        echo Installeer Python via https://www.python.org/downloads/ en probeer daarna opnieuw.
        pause
        exit /b 1
    )
)

echo ============================================
echo   DMT - De Musculatuur Tool wordt opgestart
echo ============================================
echo.

rem Installeert/updatet altijd stil de benodigdheden uit requirements.txt (niet enkel de eerste
rem keer) - zo komen latere toevoegingen (bv. een package-versie-fix) ook aan bij wie de tool
rem al eerder gebruikte, zonder dat daar iets voor moet gebeuren. Duurt maar enkele seconden
rem als alles al up-to-date is.
echo Benodigdheden controleren...
%PY% -m pip install -q -r requirements.txt

echo.
echo De tool opent zo dadelijk in je browser op http://localhost:8501
echo Laat dit venster open staan zolang je de tool gebruikt.
echo Sluit dit venster om de tool weer af te sluiten.
echo.

%PY% -m streamlit run app.py

echo.
echo De tool is gestopt. Dit venster mag je nu sluiten.
pause
