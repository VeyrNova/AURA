@echo off
setlocal EnableExtensions
title AURA - PREMIUM HUD R3 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R3_20260920_172752\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R3_20260920_172752\aura-dev-ui-premium-r3.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_R3_20260920_172752\aura-dev-ui-premium-r3.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r3.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r3.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-premium-r3.css"
)
echo [PASS] PREMIUM HUD R3 rolled back.
pause
