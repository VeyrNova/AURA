@echo off
setlocal EnableExtensions
title AURA - R3 SCREEN FIT FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX1_20260920_173346\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX1_20260920_173346\aura-dev-ui-screen-fit-r3-fix1.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R3_SCREEN_FIT_FIX1_20260920_173346\aura-dev-ui-screen-fit-r3-fix1.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix1.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix1.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-dev-ui-screen-fit-r3-fix1.css"
)
echo [PASS] R3 SCREEN FIT FIX1 rolled back.
pause
