@echo off
setlocal EnableExtensions
title AURA - R10 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\SINGLE_SEMANTIC_DOCK_R10_20260920_203848\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\SINGLE_SEMANTIC_DOCK_R10_20260920_203848\aura-single-semantic-dock-r10.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\SINGLE_SEMANTIC_DOCK_R10_20260920_203848\aura-single-semantic-dock-r10.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\SINGLE_SEMANTIC_DOCK_R10_20260920_203848\aura-single-semantic-dock-r10.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\SINGLE_SEMANTIC_DOCK_R10_20260920_203848\aura-single-semantic-dock-r10.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-single-semantic-dock-r10.js"
)
echo [PASS] R10 rolled back.
pause
