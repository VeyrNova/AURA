@echo off
setlocal EnableExtensions
title AURA - LIQUID GLASS R8 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_20260920_181732\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_20260920_181732\aura-liquid-glass-r8.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_20260920_181732\aura-liquid-glass-r8.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_20260920_181732\aura-liquid-glass-r8.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_20260920_181732\aura-liquid-glass-r8.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8.js"
)
echo [PASS] LIQUID GLASS R8 rolled back.
pause
