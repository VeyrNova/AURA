import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    property bool lightMode: false
    // AURA_CONVERSATION_CHROMIUM_PARITY_FIX13

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: 12
        color: root.lightMode ? "#F6FBFCF5" : "#FB03111B"
        border.width: 1
        border.color: root.lightMode ? "#365D879C" : "#4D6FE4F7"

        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: 0.0
                color: root.lightMode ? "#F9FCFDF7" : "#FA03111B"
            }
            GradientStop {
                position: 1.0
                color: root.lightMode ? "#EFF7FAF4" : "#FA040C17"
            }
        }

        Rectangle {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 48
            radius: 12
            color: root.lightMode ? "#EDF8FAFC" : "#F4071520"

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: root.lightMode ? "#245D8799" : "#296FE4F7"
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Rectangle {
                    width: 24
                    height: 24
                    radius: 12
                    color: root.lightMode ? "#DBF1F7F9" : "#B507222D"
                    border.width: 1
                    border.color: root.lightMode ? "#426C92A5" : "#4D6FE4F7"

                    Image {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        source: root.lightMode
                                ? auraAssetBase + "AURA_LOGO_SYMBOL_ARCTIC.svg"
                                : auraAssetBase + "AURA_LOGO_SYMBOL_NEON.svg"
                        fillMode: Image.PreserveAspectFit
                        mipmap: true
                    }
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 3

                    Text {
                        text: "AURA"
                        color: root.lightMode ? "#607584" : "#8EBCC6"
                        font.pixelSize: 6
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.2
                    }

                    Text {
                        text: "CONVERSATION EN COURS"
                        color: root.lightMode ? "#284B5E" : "#DFFAFF"
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 5

                Rectangle {
                    width: 72
                    height: 26
                    radius: 7
                    visible: coreBridge.lastAuraChars > 0
                    color: root.lightMode ? "#DFF5F9FB" : "#85051A26"
                    border.width: 1
                    border.color: root.lightMode ? "#305D8295" : "#2D6FE4F7"

                    Text {
                        anchors.centerIn: parent
                        text: "RX  " + coreBridge.lastAuraChars
                        color: root.lightMode ? "#466878" : "#82DCE8"
                        font.pixelSize: 6
                        font.letterSpacing: 0.6
                    }
                }

                Rectangle {
                    width: 27
                    height: 26
                    radius: 7
                    color: reconnectHover.hovered
                           ? (root.lightMode ? "#EAF6F9FC" : "#A5122E3B")
                           : (root.lightMode ? "#D7FFFFFF" : "#76051420")
                    border.width: 1
                    border.color: reconnectHover.hovered
                                  ? "#5D9FB2"
                                  : (root.lightMode ? "#2D5D8295" : "#2A5B8798")

                    Canvas {
                        anchors.centerIn: parent
                        width: 13
                        height: 13
                        antialiasing: true
                        onPaint: {
                            var c=getContext("2d")
                            c.clearRect(0,0,width,height)
                            c.strokeStyle=root.lightMode?"#3E6878":"#8EDCE8"
                            c.lineWidth=1.25
                            c.lineCap="round"
                            c.lineJoin="round"
                            c.beginPath()
                            c.arc(6.5,6.5,4.4,-2.25,1.85)
                            c.stroke()
                            c.beginPath()
                            c.moveTo(2.0,2.8)
                            c.lineTo(2.4,6.2)
                            c.lineTo(5.3,4.7)
                            c.stroke()
                        }
                    }

                    HoverHandler { id: reconnectHover }
                    TapHandler { onTapped: coreBridge.reconnect() }
                }

                Rectangle {
                    width: 27
                    height: 26
                    radius: 7
                    color: clearHover.hovered
                           ? (root.lightMode ? "#EAF6F9FC" : "#A5122E3B")
                           : (root.lightMode ? "#D7FFFFFF" : "#76051420")
                    border.width: 1
                    border.color: clearHover.hovered
                                  ? "#5D9FB2"
                                  : (root.lightMode ? "#2D5D8295" : "#2A5B8798")

                    Canvas {
                        anchors.centerIn: parent
                        width: 13
                        height: 13
                        antialiasing: true
                        onPaint: {
                            var c=getContext("2d")
                            c.clearRect(0,0,width,height)
                            c.strokeStyle=root.lightMode?"#5A7581":"#7996A3"
                            c.lineWidth=1.15
                            c.lineCap="round"
                            c.lineJoin="round"
                            c.beginPath()
                            c.moveTo(3.3,4.0); c.lineTo(9.8,4.0)
                            c.moveTo(4.3,4.0); c.lineTo(4.8,10.6)
                            c.lineTo(8.4,10.6); c.lineTo(8.9,4.0)
                            c.moveTo(5.2,2.6); c.lineTo(7.9,2.6)
                            c.stroke()
                        }
                    }

                    HoverHandler { id: clearHover }
                    TapHandler { onTapped: coreBridge.clearConversation() }
                }

                Rectangle {
                    width: 27
                    height: 26
                    radius: 7
                    color: closeHover.hovered
                           ? (root.lightMode ? "#EAF6F9FC" : "#A5122E3B")
                           : (root.lightMode ? "#D7FFFFFF" : "#76051420")
                    border.width: 1
                    border.color: closeHover.hovered
                                  ? "#5D9FB2"
                                  : (root.lightMode ? "#2D5D8295" : "#2A5B8798")

                    Text {
                        anchors.centerIn: parent
                        text: "×"
                        color: closeHover.hovered
                               ? (root.lightMode ? "#315A6B" : "#DFFAFF")
                               : (root.lightMode ? "#607783" : "#7F9AA6")
                        font.pixelSize: 12
                    }

                    HoverHandler { id: closeHover }
                    TapHandler { onTapped: bridge.setWorkspace("home") }
                }
            }
        }

        Item {
            id: body
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: parent.bottom

            ListView {
                id: messageList
                anchors.fill: parent
                anchors.leftMargin: root.width < 900 ? 16 : 18
                anchors.rightMargin: root.width < 900 ? 16 : 18
                anchors.topMargin: 14
                anchors.bottomMargin: errorBanner.visible ? 48 : 18
                clip: true
                spacing: 12
                model: conversationModel

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    width: 6
                }

                delegate: Item {
                    id: messageDelegate
                    width: messageList.width
                    property bool fromUser: side === "user"
                    property bool fromAura: side === "assistant"
                    property bool fromSystem: side === "system"
                    property real maxBubbleWidth: Math.min(760, messageList.width * 0.82)
                    property real minBubbleWidth: messageList.width < 620 ? 190 : 220
                    height: bubble.height + 1

                    Rectangle {
                        id: bubble
                        anchors.right: messageDelegate.fromUser ? parent.right : undefined
                        anchors.left: messageDelegate.fromUser ? undefined : parent.left

                        width: Math.min(
                            messageDelegate.maxBubbleWidth,
                            Math.max(
                                messageDelegate.minBubbleWidth,
                                Math.min(
                                    messageDelegate.maxBubbleWidth,
                                    messageText.implicitWidth + 28
                                )
                            )
                        )

                        height: messageText.paintedHeight + metaText.paintedHeight + 31
                        radius: 9

                        color: messageDelegate.fromUser
                               ? (root.lightMode ? "#E8F2F6F8" : "#E30A1322")
                               : messageDelegate.fromSystem
                                 ? (root.lightMode ? "#EEF5F7F7" : "#E40B111C")
                                 : (root.lightMode ? "#EAF7FAFB" : "#E3061F2B")

                        border.width: 1
                        border.color: messageDelegate.fromUser
                                      ? (root.lightMode ? "#305B7E93" : "#297E65EF")
                                      : messageDelegate.fromSystem
                                        ? (root.lightMode ? "#265E7A8A" : "#235B7280")
                                        : (root.lightMode ? "#34678296" : "#2E6FE4F7")

                        Text {
                            id: messageText
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: 13
                            anchors.rightMargin: 13
                            anchors.topMargin: 10
                            text: model.text
                            wrapMode: Text.Wrap
                            color: root.lightMode ? "#294555" : "#D3DCE6"
                            font.family: "Segoe UI Variable"
                            font.pixelSize: 11
                            lineHeight: 1.48
                        }

                        Text {
                            id: metaText
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.leftMargin: 13
                            anchors.bottomMargin: 8
                            text: (messageDelegate.fromUser
                                   ? "VOUS"
                                   : messageDelegate.fromAura
                                     ? "AURA"
                                     : "SYSTÈME")
                                  + "   ·   " + timestamp
                            color: messageDelegate.fromAura
                                   ? (root.lightMode ? "#438092" : "#61C6D9")
                                   : messageDelegate.fromUser
                                     ? (root.lightMode ? "#657B8A" : "#7C88AA")
                                     : (root.lightMode ? "#6A7D88" : "#677B88")
                            font.pixelSize: 6
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.75
                        }
                    }
                }

                Item {
                    anchors.fill: parent
                    visible: messageList.count === 0

                    Column {
                        anchors.centerIn: parent
                        width: Math.min(420, parent.width - 48)
                        spacing: 8

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: coreBridge.connected ? "AURA EST PRÊTE" : "AURA EST HORS LIGNE"
                            color: root.lightMode ? "#577285" : "#8A90B6"
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.25
                        }

                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: coreBridge.connected
                                  ? "La conversation apparaîtra ici. Utilise la barre AURA en bas de l’écran pour écrire ou parler."
                                  : "Reconnecte le Core AURA pour reprendre la conversation."
                            color: root.lightMode ? "#738A97" : "#566779"
                            font.pixelSize: 8
                            lineHeight: 1.45
                        }
                    }
                }

                Connections {
                    target: coreBridge
                    function onMessageAdded() {
                        messageList.positionViewAtEnd()
                    }
                }
            }

            Rectangle {
                id: errorBanner
                visible: coreBridge.lastError.length > 0
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                anchors.bottomMargin: 12
                height: 30
                radius: 8
                color: root.lightMode ? "#E9FFF2F4" : "#C31B0D16"
                border.width: 1
                border.color: root.lightMode ? "#4FCD6E85" : "#55FF6F94"

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 24
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter
                    text: coreBridge.lastError
                    color: root.lightMode ? "#8A3145" : "#FF91AA"
                    font.pixelSize: 7
                }
            }
        }
    }
}
