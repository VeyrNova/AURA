# Prepared Action UI — human live test

This test is non-destructive and must use a harmless test-owned window (for example a temporary Notepad window). Do not use an AURA, browser or other user-owned window.

## Confirm

1. Start the Native AURA runtime with the normal Windows Qt platform.
2. Open a harmless test-owned window and note its visible title.
3. In the Composer, type `minimise la fenêtre <titre exact>`.
4. Verify that the AURA confirmation card appears with a human summary, `CONFIRMER` and `ANNULER`.
5. Verify the window is still normal and has not been minimized.
6. Click `CONFIRMER` once.
7. Verify the window minimizes, the card closes and no raw HWND/PID/JSON is shown.

## Cancel

Restore the same harmless window, request minimize again and click `ANNULER`. Verify the window remains normal and the card closes.

## Double click

Request minimize again and rapidly click `CONFIRMER` twice. Verify the backend mutates the window at most once and the card reaches one terminal result.

## Voice transcript

Use an existing voice transcript with the same wording. It must show the same card and must not confirm automatically. Use the UI button for confirmation.

Expected diagnostics, when diagnostic mode is enabled, contain only safe markers such as `PREPARED_ACTION_UI_SHOW`, `PREPARED_ACTION_UI_CONFIRM`, `PREPARED_ACTION_UI_CANCEL` and `PREPARED_ACTION_UI_CLOSE`; they must not contain credentials, tokens or raw executable payloads.
