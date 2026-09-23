@echo off
setlocal EnableExtensions
title AURA - PREMIUM CINEMATIC R5 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_CINEMATIC_R5_20260920_175603\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_CINEMATIC_R5_20260920_175603\aura-premium-cinematic-r5.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_CINEMATIC_R5_20260920_175603\aura-premium-cinematic-r5.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_CINEMATIC_R5_20260920_175603\aura-premium-cinematic-r5.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_CINEMATIC_R5_20260920_175603\aura-premium-cinematic-r5.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-cinematic-r5.js"
)
echo [PASS] PREMIUM CINEMATIC R5 rolled back.
pause
