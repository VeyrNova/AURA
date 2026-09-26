import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "../components"

Item {
    id: root

    // AURA_MUSIC_PIXELPLAYER_EXPERIENCE_FIX36
    // AURA_NATIVE_MUSIC_MINIPLAYER_R13
    property bool lightMode: false
    property Item backdropSource: null

    signal closeRequested()
    signal openFullRequested()

    // AURA_NATIVE_MUSIC_MINIPLAYER_TRANSPORT_R15 START
    // Keep the validated 452 px desktop size, but contract slightly
    // when the host window approaches its minimum width.
    width: Math.max(
        408,
        Math.min(
            452,
            parent ? parent.width * 0.36 : 452
        )
    )
    height: 104
    readonly property bool r15Compact: width < 438
    // AURA_NATIVE_MUSIC_MINIPLAYER_TRANSPORT_R15 END

    // R13: shared playing ambience, opacity only — no image scale.
    property real r13PlayingPulse: 0.0

    SequentialAnimation on r13PlayingPulse {
        running: musicBridge.playing && root.visible
        loops: Animation.Infinite

        NumberAnimation {
            from: 0.02
            to: 0.11
            duration: 1050
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            from: 0.11
            to: 0.02
            duration: 1150
            easing.type: Easing.InOutSine
        }
    }

    LiquidGlass {
        anchors.fill: parent
        backdropSource: root.backdropSource
        sourceX: root.x
        sourceY: root.y
        lightMode: root.lightMode
        accent: "#A66CFF"
        cornerRadius: 20
        blurStrength: 0.95
        saturationBoost: 0.34
        darkOpacity: 0.92
        lightOpacity: 0.92
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: 21
        color: "transparent"
        border.width: 1
        border.color: musicBridge.playing ? "#785DEBFF" : "#675DDFF6"

        Behavior on border.color {
            ColorAnimation { duration: 170 }
        }
    }

    Row {
        anchors.fill: parent
        anchors.margins: root.r15Compact ? 9 : 11
        spacing: root.r15Compact ? 8 : 11

        Rectangle {
            id: r13CoverFrame
            width: root.r15Compact ? 68 : 80
            height: width
            radius: root.r15Compact ? 14 : 16
            color: "#720A1725"
            border.width: musicBridge.playing ? 2 : 1
            border.color: musicBridge.playing ? "#74EFFF" : "#5C8669D6"

            Behavior on border.color {
                ColorAnimation { duration: 170 }
            }

            Image {
                id: r13CoverArt
                anchors.fill: parent
                anchors.margins: musicBridge.currentCover.length ? 2 : 19
                source: musicBridge.currentCover.length
                        ? musicBridge.currentCover
                        : auraAssetBase + "music-note-premium.svg"
                fillMode: musicBridge.currentCover.length
                          ? Image.PreserveAspectCrop
                          : Image.PreserveAspectFit
                smooth: true
                mipmap: true

                layer.enabled: true
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: ShaderEffectSource {
                        sourceItem: Rectangle {
                            width: r13CoverArt.width
                            height: r13CoverArt.height
                            radius: musicBridge.currentCover.length ? 14 : 10
                            color: "white"
                        }
                    }
                }
            }

            Rectangle {
                anchors.fill: r13CoverArt
                radius: musicBridge.currentCover.length ? 14 : 10
                color: "#126B4CFF"
                opacity: musicBridge.playing
                         ? (0.035 + root.r13PlayingPulse * 0.35)
                         : 0.0
                z: r13CoverArt.z + 2
            }

            Rectangle {
                anchors.fill: r13CoverArt
                radius: musicBridge.currentCover.length ? 14 : 10
                color: "transparent"
                border.width: 1
                border.color: "#C9F8FF"
                opacity: musicBridge.playing
                         ? (0.12 + root.r13PlayingPulse)
                         : 0.07
                z: r13CoverArt.z + 3

                Behavior on opacity {
                    NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                }
            }

            TapHandler {
                onTapped: root.openFullRequested()
            }
        }

        Column {
            // R15: consume the exact width left by cover, transport and actions.
            width: Math.max(
                108,
                parent.width
                - r13CoverFrame.width
                - r15Transport.width
                - r15Actions.width
                - (parent.spacing * 3)
            )
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4

            Text {
                width: parent.width
                text: musicBridge.currentTitle.length
                      ? musicBridge.currentTitle
                      : "Aucun média"
                color: root.lightMode ? "#173F56" : "#F0FCFF"
                font.pixelSize: 10
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: musicBridge.currentArtist.length
                      ? musicBridge.currentArtist
                      : "Bibliothèque locale"
                color: root.lightMode ? "#607D8D" : "#7895A6"
                font.pixelSize: 7
                elide: Text.ElideRight
            }

            Row {
                width: parent.width
                height: 8
                spacing: 5

                Rectangle {
                    width: 5
                    height: 5
                    radius: 3
                    anchors.verticalCenter: parent.verticalCenter
                    color: musicBridge.playing ? "#74EFFF" : "#607D8D"
                    opacity: musicBridge.playing
                             ? (0.72 + root.r13PlayingPulse)
                             : 0.58
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: musicBridge.playing ? "EN LECTURE" : "EN PAUSE"
                    color: musicBridge.playing ? "#9EF5FF" : "#7895A6"
                    font.pixelSize: 6
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.7
                }
            }

            Rectangle {
                width: parent.width
                height: 4
                radius: 2
                color: "#30304756"

                Rectangle {
                    id: r13ProgressFill
                    width: parent.width * Math.max(
                        0,
                        Math.min(1, musicBridge.progress)
                    )
                    height: parent.height
                    radius: 2
                    color: musicBridge.playing ? "#74EFFF" : "#68889B"

                    Behavior on width {
                        NumberAnimation { duration: 120; easing.type: Easing.OutQuad }
                    }
                    Behavior on color {
                        ColorAnimation { duration: 160 }
                    }
                }
            }

            Text {
                text: musicBridge.positionLabel
                      + "  /  "
                      + musicBridge.durationLabel
                color: "#7693A4"
                font.pixelSize: 7
            }
        }

        Row {
            id: r15Transport
            width: root.r15Compact ? 112 : 126
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.r15Compact ? 5 : 6

            Rectangle {
                id: r15PreviousButton
                width: root.r15Compact ? 30 : 34
                height: width
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: r15PreviousHover.hovered ? "#35132636" : "#4207131F"
                border.width: 1
                border.color: r15PreviousHover.hovered ? "#5574EFFF" : "#376B859F"

                Behavior on color {
                    ColorAnimation { duration: 140 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 140 }
                }

                Image {
                    anchors.centerIn: parent
                    width: root.r15Compact ? 13 : 15
                    height: width
                    source: auraAssetBase + "music-prev-premium.svg"
                    fillMode: Image.PreserveAspectFit
                }

                HoverHandler {
                    id: r15PreviousHover
                }

                TapHandler {
                    onTapped: musicBridge.previous()
                }
            }

            Rectangle {
                id: r13PlayButton
                width: root.r15Compact ? 42 : 46
                height: width
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: r13PlayHover.hovered
                       ? (musicBridge.playing ? "#4B153D4C" : "#3913293A")
                       : (musicBridge.playing ? "#35102431" : "#5D07131F")
                border.width: musicBridge.playing ? 2 : 1
                border.color: musicBridge.playing
                              ? "#74EFFF"
                              : (r13PlayHover.hovered ? "#66D9F3" : "#4A74EFFF")

                Behavior on color {
                    ColorAnimation { duration: 140 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 140 }
                }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 4
                    radius: width / 2
                    color: "#126B4CFF"
                    opacity: musicBridge.playing
                             ? (0.06 + root.r13PlayingPulse * 0.45)
                             : (r13PlayHover.hovered ? 0.07 : 0.0)

                    Behavior on opacity {
                        NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                    }
                }

                Image {
                    anchors.centerIn: parent
                    width: root.r15Compact ? 18 : 20
                    height: width
                    source: auraAssetBase
                            + (musicBridge.playing
                               ? "music-pause-premium.svg"
                               : "music-play-premium.svg")
                    fillMode: Image.PreserveAspectFit
                }

                HoverHandler {
                    id: r13PlayHover
                }

                TapHandler {
                    onTapped: musicBridge.togglePlay()
                }
            }

            Rectangle {
                id: r15NextButton
                width: root.r15Compact ? 30 : 34
                height: width
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: r13NextHover.hovered ? "#35132636" : "#4207131F"
                border.width: 1
                border.color: r13NextHover.hovered ? "#5574EFFF" : "#376B859F"

                Behavior on color {
                    ColorAnimation { duration: 140 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 140 }
                }

                Image {
                    anchors.centerIn: parent
                    width: root.r15Compact ? 13 : 15
                    height: width
                    source: auraAssetBase + "music-next-premium.svg"
                    fillMode: Image.PreserveAspectFit
                }

                HoverHandler {
                    id: r13NextHover
                }

                TapHandler {
                    onTapped: musicBridge.next()
                }
            }
        }

        Column {
            id: r15Actions
            width: root.r15Compact ? 30 : 34
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.r15Compact ? 5 : 7

            // AURA_NATIVE_MUSIC_MINIPLAYER_ACTIONS_R14_FIX2 START
            Rectangle {
                id: r14ExpandButton
                width: root.r15Compact ? 28 : 32
                height: width
                radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                color: r14ExpandHover.hovered ? "#351B3946" : "#220B1A27"
                border.width: 1
                border.color: r14ExpandHover.hovered ? "#83F3FF" : "#5574EFFF"

                Behavior on color {
                    ColorAnimation { duration: 130 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 130 }
                }

                Item {
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    opacity: r14ExpandHover.hovered ? 1.0 : 0.82

                    Rectangle { x: 0; y: 0; width: 5; height: 1.5; radius: 1; color: "#BDF9FF" }
                    Rectangle { x: 0; y: 0; width: 1.5; height: 5; radius: 1; color: "#BDF9FF" }

                    Rectangle { x: 9; y: 0; width: 5; height: 1.5; radius: 1; color: "#BDF9FF" }
                    Rectangle { x: 12.5; y: 0; width: 1.5; height: 5; radius: 1; color: "#BDF9FF" }

                    Rectangle { x: 0; y: 12.5; width: 5; height: 1.5; radius: 1; color: "#BDF9FF" }
                    Rectangle { x: 0; y: 9; width: 1.5; height: 5; radius: 1; color: "#BDF9FF" }

                    Rectangle { x: 9; y: 12.5; width: 5; height: 1.5; radius: 1; color: "#BDF9FF" }
                    Rectangle { x: 12.5; y: 9; width: 1.5; height: 5; radius: 1; color: "#BDF9FF" }

                    Behavior on opacity {
                        NumberAnimation { duration: 120 }
                    }
                }

                HoverHandler {
                    id: r14ExpandHover
                }

                TapHandler {
                    onTapped: root.openFullRequested()
                }
            }

            Rectangle {
                id: r14CloseButton
                width: root.r15Compact ? 28 : 32
                height: width
                radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                color: r14CloseHover.hovered ? "#3D142A34" : "#22100A18"
                border.width: 1
                border.color: r14CloseHover.hovered ? "#FF79C9" : "#6A9A4B78"

                Behavior on color {
                    ColorAnimation { duration: 130 }
                }
                Behavior on border.color {
                    ColorAnimation { duration: 130 }
                }

                Item {
                    anchors.centerIn: parent
                    width: 14
                    height: 14

                    Rectangle {
                        anchors.centerIn: parent
                        width: 15
                        height: 1.8
                        radius: 1
                        rotation: 45
                        color: r14CloseHover.hovered ? "#FFD4EE" : "#E5A0C1"
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 15
                        height: 1.8
                        radius: 1
                        rotation: -45
                        color: r14CloseHover.hovered ? "#FFD4EE" : "#E5A0C1"
                    }
                }

                HoverHandler {
                    id: r14CloseHover
                }

                TapHandler {
                    onTapped: root.closeRequested()
                }
            }
            // AURA_NATIVE_MUSIC_MINIPLAYER_ACTIONS_R14_FIX2 END
        }
    }
}
