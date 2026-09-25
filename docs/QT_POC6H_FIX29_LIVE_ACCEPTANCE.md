# AURA Qt POC6H — FIX29 Live Acceptance Checkpoint

Date: 2026-09-25  
Repository: `VeyrNova/AURA`  
Status: **validated native Qt checkpoint — not yet production replacement**

## Validated architecture

- Qt Quick / QML is the visible AURA shell for this POC.
- The existing AURA Python Core remains authoritative and runs headless.
- Chromium/Edge is not used as the visible UI for this POC.
- The native shell has been progressively aligned with the Chromium RC4.2 visual language rather than replacing the Core logic.

## Validated UI / functional areas

The following areas have been exercised during the POC6H validation sequence:

- HOME with the native neural orb and AURA chrome.
- Conversation connected to the headless Core.
- Memory workspace.
- Productivity workspace / Tasks.
- Agenda / Google Calendar.
- Parameters.
- Diagnostics.

## Google productivity integration

Validated during the FIX21–FIX29 sequence:

- Google Calendar account connection and synchronization.
- Google Calendar events displayed in the native Agenda.
- Google Calendar event creation.
- Google Calendar event selection and inline editing.
- Google Tasks synchronization.
- Google Tasks creation.
- Google Tasks edit / completion / deletion actions.
- Visual source identification upgraded in FIX29 using the Google favicon treatment.

## UI validation through FIX29

The validated native checkpoint includes:

- wider premium Productivity and Agenda drawers;
- Chromium-inspired dark glass visual direction;
- improved action icon readability;
- corrected drawer overflow issues;
- corrected calendar add-button overflow;
- corrected task action-button overflow;
- refined visual hierarchy for Tasks and Calendar;
- Google source badges/favicons integrated into the native Qt views.

## Important scope boundary

This checkpoint validates the current native Qt migration state. It does **not** declare full feature parity with the production Chromium RC4.2 UI.

Remaining Chromium routes/panels and behavioral parity must be audited and migrated incrementally before any production shell replacement.

## Baseline

Use **POC6H + FIX29** as the next Qt migration baseline. Do not regress the validated Google Tasks / Calendar integration or the current Home / Conversation / Memory / Productivity / Agenda / Parameters / Diagnostics behavior.

Next step: perform a read-only Chromium-vs-Qt parity audit and migrate the remaining routes by gap priority.
