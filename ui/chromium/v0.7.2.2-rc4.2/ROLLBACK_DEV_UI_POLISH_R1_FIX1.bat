@echo off
setlocal EnableExtensions
title AURA - DEV UI POLISH R1 FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\POLISH_R1_FIX1_20260920_171834\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\POLISH_R1_FIX1_20260920_171834\aura-dev-ui-polish-r1.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\POLISH_R1_FIX1_20260920_171834\aura-dev-ui-polish-r1.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-polish-r1.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-polish-r1.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-polish-r1.css"
)
echo [PASS] DEV UI POLISH R1 FIX1 rolled back.
echo Launch RUN_AURA_DEV_UI.bat to verify.
pause
