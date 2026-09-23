@echo off
setlocal EnableExtensions
title AURA - THEME R7 FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_R7_FIX1_20260920_181145\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_R7_FIX1_20260920_181145\aura-theme-dualmode-r7-fix1.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\THEME_R7_FIX1_20260920_181145\aura-theme-dualmode-r7-fix1.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7-fix1.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7-fix1.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-theme-dualmode-r7-fix1.css"
)
echo [PASS] THEME R7 FIX1 rolled back.
pause
