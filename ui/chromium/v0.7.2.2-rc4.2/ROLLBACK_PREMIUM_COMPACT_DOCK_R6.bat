@echo off
setlocal EnableExtensions
title AURA - PREMIUM COMPACT DOCK R6 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_COMPACT_DOCK_R6_20260920_175802\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_COMPACT_DOCK_R6_20260920_175802\aura-premium-compact-dock-r6.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\PREMIUM_COMPACT_DOCK_R6_20260920_175802\aura-premium-compact-dock-r6.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-compact-dock-r6.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-compact-dock-r6.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-premium-compact-dock-r6.css"
)
echo [PASS] PREMIUM COMPACT DOCK R6 rolled back.
pause
