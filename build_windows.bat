@echo off
setlocal
cd /d "%~dp0"
python -m unittest discover -s tests -q
if errorlevel 1 exit /b 1
python -m PyInstaller aiditor_plus_windows.spec --noconfirm
if errorlevel 1 exit /b 1
iscc aiditor_plus_setup.iss
if errorlevel 1 exit /b 1
echo Ready: dist\AIditorPlus_Setup.exe
