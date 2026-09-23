@echo off
setlocal EnableExtensions
title AURA - R3 SCREEN FIT FIX2 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX2_20260920_174317\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX2_20260920_174317\aura-dev-ui-screen-fit-r3-fix2.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX2_20260920_174317\aura-dev-ui-screen-fit-r3-fix2.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix2.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix2.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix2.css"
)
echo [PASS] R3 SCREEN FIT FIX2 rolled back.
pause
