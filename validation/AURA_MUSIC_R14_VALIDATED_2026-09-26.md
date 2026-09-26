# AURA Music R14 - Validated milestone

Date: 2026-09-26

## Status
VALIDATED

## Baseline
R14 is based on:
`validation/aura-music-r13-20260926-185123`

## Scope
Native Qt/QML adaptive global music mini-player.

Validated sources:
- `app/qml/Main.qml`
- `app/qml/components/MusicSubdock.qml`

## R14 behavior
- Adaptive mini-player safe-zone positioning.
- Right-side placement preferred when space is available.
- Left-side fallback when required.
- Above-dock/composer fallback when side placement cannot fit.
- Smooth x/y movement during resize.
- Fade-based appearance/disappearance without scale transforms.
- Premium expand and close controls fully inside the player.
- Expand control uses cyan vector corner marks.
- Close control uses restrained magenta vector X.
- R13 playback-state behavior preserved.
- No audio/backend modification.

## Runtime validation
User confirmed R14 after visual and functional testing.

## SHA256
Main.qml:
`E7B95E62BC45FA954C4D973D3E165A192FC80A85CA6B22A40193E597A17A79DA`

MusicSubdock.qml:
`8B0BDA898A55FFC1FE9C8CF209CAF40344DB9E220B587A4C250C655D076278F6`
