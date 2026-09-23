@echo off
setlocal EnableExtensions
title AURA - BOOT RECOVERY FIX3 ROLLBACK
copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\BOOT_RECOVERY_FIX3_20260920_192728\index.html" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\index.html" >nul
if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\BOOT_RECOVERY_FIX3_20260920_192728\aura-boot-isolation-recovery-fix3.css" (
  copy /Y "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\.dev_ui_backups\BOOT_RECOVERY_FIX3_20260920_192728\aura-boot-isolation-recovery-fix3.css" "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-boot-isolation-recovery-fix3.css" >nul
) else (
  if exist "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-boot-isolation-recovery-fix3.css" del /q "C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\dist\assets\aura-boot-isolation-recovery-fix3.css"
)
echo [PASS] BOOT RECOVERY FIX3 rolled back.
pause
