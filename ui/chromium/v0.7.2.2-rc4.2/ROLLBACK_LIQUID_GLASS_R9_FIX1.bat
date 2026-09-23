@echo off
setlocal EnableExtensions
title AURA - R9 FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R9_FIX1_20260921_184722\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R9_FIX1_20260921_184722\aura-liquid-glass-stable-r9-fix1.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R9_FIX1_20260921_184722\aura-liquid-glass-stable-r9-fix1.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R9_FIX1_20260921_184722\aura-liquid-glass-stable-r9-fix1.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R9_FIX1_20260921_184722\aura-liquid-glass-stable-r9-fix1.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-stable-r9-fix1.js"
)
echo [PASS] R9 FIX1 rolled back.
pause
