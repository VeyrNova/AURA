@echo off
setlocal EnableExtensions
title AURA - PREMIUM MINIMAL R4 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_MINIMAL_R4_20260920_175243\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_MINIMAL_R4_20260920_175243\aura-premium-minimal-r4.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_MINIMAL_R4_20260920_175243\aura-premium-minimal-r4.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-minimal-r4.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-minimal-r4.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-minimal-r4.css"
)
echo [PASS] PREMIUM MINIMAL R4 rolled back.
echo Launch RUN_AURA_DEV_UI.bat to verify.
pause
