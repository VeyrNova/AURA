@echo off
setlocal EnableExtensions
title AURA - R8 FIX2 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX2_20260920_192112\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX2_20260920_192112\aura-liquid-glass-r8-fix2.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX2_20260920_192112\aura-liquid-glass-r8-fix2.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX2_20260920_192112\aura-liquid-glass-r8-fix2.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\LIQUID_GLASS_R8_FIX2_20260920_192112\aura-liquid-glass-r8-fix2.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-liquid-glass-r8-fix2.js"
)
echo [PASS] R8 FIX2 rolled back.
pause
