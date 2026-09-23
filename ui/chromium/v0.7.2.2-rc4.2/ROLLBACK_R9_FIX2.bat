@echo off
setlocal EnableExtensions
title AURA - R9 FIX2 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R9_FIX2_20260920_201552\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R9_FIX2_20260920_201552\aura-r9-fix2-semantic-panel-light.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R9_FIX2_20260920_201552\aura-r9-fix2-semantic-panel-light.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R9_FIX2_20260920_201552\aura-r9-fix2-semantic-panel-light.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\R9_FIX2_20260920_201552\aura-r9-fix2-semantic-panel-light.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-r9-fix2-semantic-panel-light.js"
)
echo [PASS] R9 FIX2 rolled back.
pause
