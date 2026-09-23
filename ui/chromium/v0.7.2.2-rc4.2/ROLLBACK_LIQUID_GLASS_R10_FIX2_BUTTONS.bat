@echo off
setlocal EnableExtensions
title AURA - R10 FIX2 ROUTER ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R10_FIX2_BUTTONS_20260921_190654\aura-liquid-glass-r10.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r10.js" >nul
if errorlevel 1 (
  echo [FAIL] Rollback failed.
  pause
  exit /b 1
)
echo [PASS] R10 FIX2 router rolled back.
pause
