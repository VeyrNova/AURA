@echo off
setlocal EnableExtensions
title AURA - LIQUID GLASS R8 FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX1_20260920_182101\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX1_20260920_182101\aura-liquid-glass-r8-fix1.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX1_20260920_182101\aura-liquid-glass-r8-fix1.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX1_20260920_182101\aura-liquid-glass-r8-fix1.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX1_20260920_182101\aura-liquid-glass-r8-fix1.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix1.js"
)
echo [PASS] LIQUID GLASS R8 FIX1 rolled back.
pause
