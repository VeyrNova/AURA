import QtQuick

Item {
    id: root
    property bool lightMode: false
    property real safeLeft: 18
    property real safeRight: 10
    readonly property color panel: root.lightMode ? "#EAF4F7" : "#07131E"
    readonly property color card: root.lightMode ? "#DCECF1" : "#0A202D"
    readonly property color text0: root.lightMode ? "#17394D" : "#D8F7FF"
    readonly property color text1: root.lightMode ? "#557487" : "#84A8B7"
    readonly property color accent: root.lightMode ? "#168897" : "#74EFFF"

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: root.safeLeft
        anchors.rightMargin: root.safeRight
        radius: 16
        color: root.panel
        border.width: 1
        border.color: root.lightMode ? "#4B7190" : "#1C85A8"

        Item {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 18
            height: 48

            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text { text: "AURA NATIVE · CONVERSATION"; color: root.text0; font.pixelSize: 18; font.letterSpacing: 1.5 }
                Text { text: "Conversation locale · available   ·   " + ((coreBridge.agentProvider || coreBridge.activeProvider) ? (coreBridge.agentProvider || coreBridge.activeProvider).toUpperCase() + ((coreBridge.agentModel || coreBridge.activeModel) ? " · " + (coreBridge.agentModel || coreBridge.activeModel) : "") : "aucun fournisseur sélectionné"); color: root.text1; font.pixelSize: 9 }
                Text { visible: coreBridge.agentErrorMessage.length > 0; text: coreBridge.agentErrorMessage; color: root.lightMode ? "#9A3F54" : "#F2A4B8"; font.pixelSize: 9; elide: Text.ElideRight; width: header.width - 110 }
                Text { visible: coreBridge.localCommandMessage.length > 0; text: coreBridge.localCommandMessage; color: root.text1; font.pixelSize: 9; elide: Text.ElideRight; width: header.width - 110 }
            }

            Rectangle {
                id: clearAction
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 94; height: 28; radius: 9
                color: clearTap.pressed ? (root.lightMode ? "#BDDCE4" : "#123D4B")
                     : (clearTap.hovered ? (root.lightMode ? "#D2E9EE" : "#0D3040") : root.card)
                border.width: 1
                border.color: root.lightMode ? "#5E96A6" : "#27718A"
                opacity: coreBridge.messageCount > 0 ? 1.0 : 0.52
                Text { anchors.centerIn: parent; text: "EFFACER"; color: root.lightMode ? "#28566A" : root.accent; font.pixelSize: 8; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                TapHandler {
                    id: clearTap
                    enabled: coreBridge.messageCount > 0
                    onTapped: coreBridge.clearConversation()
                }
            }
        }

        ListView {
            id: messages
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 14
            anchors.bottomMargin: 22
            clip: true
            spacing: 10
            model: coreBridge.messages

            footer: Item {
                width: messages.width
                height: draftCard.visible ? draftCard.height + 10 : 0
                Rectangle {
                    id: draftCard
                    visible: coreBridge.agentState === "responding" && coreBridge.agentStream.length > 0
                    anchors.right: parent.right
                    width: Math.min(parent.width, Math.max(180, draftText.implicitWidth + 30))
                    height: Math.max(50, draftText.implicitHeight + 24)
                    radius: 12
                    color: root.lightMode ? "#D4ECF1" : "#0D2A38"
                    border.width: 1
                    border.color: root.lightMode ? "#6B9EAE" : "#236A82"
                    Text {
                        id: draftText
                        anchors.fill: parent
                        anchors.margins: 12
                        text: "AURA · " + coreBridge.agentStream
                        color: root.text0
                        wrapMode: Text.Wrap
                        font.pixelSize: 12
                    }
                }
            }

            Connections {
                target: coreBridge
                function onAgentStreamChanged() { messages.positionViewAtEnd() }
            }

            delegate: Item {
                required property var modelData
                width: messages.width
                height: messageCard.height
                Rectangle {
                    id: messageCard
                    anchors.right: parent.right
                    width: Math.min(parent.width, Math.max(180, messageText.implicitWidth + 30))
                    height: Math.max(50, messageText.implicitHeight + 24)
                    radius: 12
                    color: root.lightMode ? "#D4ECF1" : "#0D2A38"
                    border.width: 1
                    border.color: root.lightMode ? "#6B9EAE" : "#236A82"
                    Text {
                        id: messageText
                        anchors.fill: parent
                        anchors.margins: 12
                        text: modelData.role.toUpperCase() + " · " + modelData.content
                        color: root.text0
                        wrapMode: Text.Wrap
                        font.pixelSize: 12
                    }
                }
            }

            Text { anchors.centerIn: parent; visible: coreBridge.messageCount === 0; text: "Aucun message local. Aucune réponse assistant n’est simulée."; color: root.text1; font.pixelSize: 12 }
        }
    }

    Component.onCompleted: coreBridge.refreshConversation()
}
