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

    width: 452
    height: 104

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
        anchors.margins: 11
        spacing: 11

        Rectangle {
            id: r13CoverFrame
            width: 80
            height: 80
            radius: 16
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
            width: parent.width - 215
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
            width: 102
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            Rectangle {
                id: r13PlayButton
                width: 46
                height: 46
                radius: 23
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
                    width: 20
                    height: 20
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
                width: 40
                height: 40
                radius: 20
                anchors.verticalCenter: parent.verticalCenter
                color: r13NextHover.hovered ? "#35132636" : "#5207131F"
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
                    width: 17
                    height: 17
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
            width: 24
            anchors.verticalCenter: parent.verticalCenter
            spacing: 5

            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "↗"
                color: "#9EEAF6"
                font.pixelSize: 16

                TapHandler {
                    onTapped: root.openFullRequested()
                }
            }

            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "×"
                color: "#A7C9D4"
                font.pixelSize: 14

                TapHandler {
                    onTapped: root.closeRequested()
                }
            }
        }
    }
}
