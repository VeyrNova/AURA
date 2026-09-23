@echo off
setlocal EnableExtensions
title AURA - UI INTERACTION R10 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\UI_INTERACTION_R10_20260920_195207\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\UI_INTERACTION_R10_20260920_195207\aura-ui-interaction-r10.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\UI_INTERACTION_R10_20260920_195207\aura-ui-interaction-r10.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\UI_INTERACTION_R10_20260920_195207\aura-ui-interaction-r10.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\UI_INTERACTION_R10_20260920_195207\aura-ui-interaction-r10.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-ui-interaction-r10.js"
)
echo [PASS] UI INTERACTION R10 rolled back.
pause
