@echo off
setlocal EnableExtensions
title AURA - CONSOLIDATION R10 FIX1 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\VERSION" copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\VERSION" "C:\AURA GPT version\VERSION" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\AURA_ROADMAP_CURRENT.md" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\AURA_ROADMAP_CURRENT.md" "C:\AURA GPT version\docs\AURA_ROADMAP_CURRENT.md" >nul
) else (
  if exist "C:\AURA GPT version\docs\AURA_ROADMAP_CURRENT.md" del /q "C:\AURA GPT version\docs\AURA_ROADMAP_CURRENT.md"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\aura-consolidation-r10.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\aura-consolidation-r10.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.css"
)
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\aura-consolidation-r10.js" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\CONSOLIDATION_R10_FIX1_20260920_205142\aura-consolidation-r10.js" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.js" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.js" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-consolidation-r10.js"
)
echo [PASS] CONSOLIDATION R10 rolled back.
pause
