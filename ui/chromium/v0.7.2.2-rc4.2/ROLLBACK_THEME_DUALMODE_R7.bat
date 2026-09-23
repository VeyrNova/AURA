@echo off
setlocal EnableExtensions
title AURA - THEME DUALMODE R7 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_DUALMODE_R7_20260920_180607\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_DUALMODE_R7_20260920_180607\aura-theme-dualmode-r7.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_DUALMODE_R7_20260920_180607\aura-theme-dualmode-r7.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_DUALMODE_R7_20260920_180607\aura-theme-dualmode-r7.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_DUALMODE_R7_20260920_180607\aura-theme-dualmode-r7.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7.js"
)
echo [PASS] THEME DUALMODE R7 rolled back.
pause
