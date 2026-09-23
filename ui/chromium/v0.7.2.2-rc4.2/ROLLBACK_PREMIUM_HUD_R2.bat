@echo off
setlocal EnableExtensions
title AURA - PREMIUM HUD R2 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R2_20260920_172532\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R2_20260920_172532\aura-dev-ui-premium-r2.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R2_20260920_172532\aura-dev-ui-premium-r2.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r2.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r2.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r2.css"
)
echo [PASS] PREMIUM HUD R2 rolled back.
echo Launch RUN_AURA_DEV_UI.bat to verify.
pause
