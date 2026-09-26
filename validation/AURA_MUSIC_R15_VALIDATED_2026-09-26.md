# AURA Music R15 - Validated milestone

Date: 2026-09-26

## Status
VALIDATED

## Baseline
R15 is based on:
`validation/aura-music-r14-20260926-192848`

## Scope
Native Qt/QML global music mini-player.

Validated sources:
- `app/qml/Main.qml`
- `app/qml/components/MusicSubdock.qml`

## R15 behavior
- Complete Previous / Play-Pause / Next transport.
- R14 Expand and Close controls preserved.
- Responsive compact mode for constrained widths.
- Dynamic metadata width based on remaining space.
- Cover and controls contract by geometry, without scale transforms.
- R14 safe-zone positioning preserved.
- R13 playing-state ambience preserved.
- No audio/backend modification.

## Runtime validation
User confirmed R15 after functional testing.

## SHA256
Main.qml:
`E7B95E62BC45FA954C4D973D3E165A192FC80A85CA6B22A40193E597A17A79DA`

MusicSubdock.qml:
`EF41BEFE1D8C4B4C9F3D7358DA8BDF7E411D24C8ABC285302C227A82EA9D851A`
