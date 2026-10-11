import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Item {
    id: root
    focus: true

    property Item backdropSource: null
    property bool lightMode: false
    // A lingering empty TextArea focus must not keep the composer expanded.
    // Large mode is reserved for real text entry; hover gets only medium mode.
    property bool writing: input.activeFocus && input.text.trim().length > 0
    property bool hoverIntent: hover.hovered && !writing
    property real lensX: 0.50
    property real lensY: 0.50

    Connections {
        target: runtimeMode === "native" ? voiceBridge : null
        function onStateChanged() {
            if (voiceBridge)
                voiceBridge.diagnosticTrace("PTT_QML_STATE_RECEIVED=" + voiceBridge.state)
        }
    }
    // Native local conversation accepts user messages before an agent exists.
    // interactionReady remains reserved for agent and voice capabilities.
    readonly property bool nativeConversationReady: runtimeMode === "native"
                                                 && coreBridge.connected
                                                 && coreBridge.conversationAvailable
    readonly property bool textSubmissionReady: runtimeMode === "native"
                                                 ? nativeConversationReady
                                                 : coreBridge.connected && coreBridge.interactionReady

    function releaseComposerFocus() {
        input.focus = false
        root.forceActiveFocus(Qt.OtherFocusReason)
    }

    // AURA_MODULES_NATIVE_FIX30
    function prefill(value) {
        var nextValue = String(value || "")
        if (!nextValue.length)
            return
        if (!input.text.trim().length)
            input.text = nextValue
        input.forceActiveFocus(Qt.OtherFocusReason)
    }

    width: writing
           ? Math.min(1040, parent.width - 48)
           : hoverIntent
             ? Math.min(740, parent.width - 76)
             : Math.min(580, parent.width - 100)

    height: writing ? 64 : hoverIntent ? 50 : 44

    Behavior on width {
        NumberAnimation {
            duration: 320
            easing.type: Easing.OutCubic
        }
    }
    Behavior on height {
        NumberAnimation {
            duration: 280
            easing.type: Easing.OutCubic
        }
    }

    LiquidGlass {
        anchors.fill: parent
        backdropSource: root.backdropSource
        sourceX: root.x
        sourceY: root.y
        lightMode: root.lightMode
        cornerRadius: root.writing ? 20 : 17
        blurStrength: 0.75
        saturationBoost: 0.18
        lensX: root.lensX
        lensY: root.lensY
    }

    HoverHandler {
        id: hover
        onHoveredChanged: {
            if (!hovered) {
                root.lensX = 0.50
                root.lensY = 0.50
                if (input.text.trim().length === 0)
                    root.releaseComposerFocus()
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        z: 0

        onPositionChanged: function(mouse) {
            root.lensX = Math.max(0, Math.min(1, mouse.x / Math.max(1, width)))
            root.lensY = Math.max(0, Math.min(1, mouse.y / Math.max(1, height)))
        }

        onExited: {
            root.lensX = 0.50
            root.lensY = 0.50
            if (input.text.trim().length === 0)
                root.releaseComposerFocus()
        }
    }

    Row {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 7

        Rectangle {
            width: 34; height: 34; radius: 10
            anchors.verticalCenter: parent.verticalCenter
            color: root.lightMode ? "#EFFFFFFF" : "#80071320"
            border.width: 1
            border.color: root.lightMode ? "#3D2F84A7" : "#2679DFF7"

            Canvas {
                anchors.centerIn: parent
                width: 18; height: 18
                antialiasing: true
                renderTarget: Canvas.FramebufferObject
                onPaint: {
                    var c = getContext("2d")
                    c.clearRect(0, 0, width, height)
                    c.save()
                    c.translate(width * 0.54, height * 0.48)
                    c.rotate(-0.72)
                    c.translate(-width * 0.54, -height * 0.48)
                    c.strokeStyle = root.lightMode ? "#15516A" : "#83E8F8"
                    c.lineWidth = 1.55
                    c.lineCap = "round"
                    c.lineJoin = "round"

                    c.beginPath()
                    c.moveTo(12.8, 5.1)
                    c.quadraticCurveTo(14.9, 7.2, 13.5, 9.7)
                    c.lineTo(8.3, 14.9)
                    c.quadraticCurveTo(6.0, 17.2, 3.7, 14.8)
                    c.quadraticCurveTo(1.4, 12.5, 3.7, 10.2)
                    c.lineTo(9.4, 4.5)
                    c.quadraticCurveTo(11.7, 2.2, 14.0, 4.5)
                    c.stroke()

                    c.beginPath()
                    c.moveTo(10.8, 6.4)
                    c.lineTo(6.0, 11.2)
                    c.quadraticCurveTo(4.9, 12.3, 5.9, 13.4)
                    c.quadraticCurveTo(7.0, 14.5, 8.1, 13.4)
                    c.lineTo(12.5, 9.0)
                    c.stroke()
                    c.restore()
                }
            }
        }

        Item {
            width: parent.width - 118
            height: parent.height - 6
            anchors.verticalCenter: parent.verticalCenter

            TextArea {
                id: input
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: root.writing ? parent.height : 21
                padding: 0
                background: null
                color: root.lightMode ? "#17394D" : "#D4F0F8"
                placeholderTextColor: root.lightMode ? "#708B9A" : "#7094A8"
                placeholderText: runtimeMode === "native" ? "Écrire un message local..." : (coreBridge.connected
                                 ? (coreBridge.interactionReady ? "Écris à AURA..." : "AURA initialise le Core...")
                                 : "AURA Core hors ligne...")
                font.family: "Segoe UI Variable"
                font.pixelSize: 10
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                enabled: root.textSubmissionReady
                opacity: enabled ? 1.0 : .56

                Keys.onReturnPressed: function(event) {
                    if ((event.modifiers & Qt.ShiftModifier) !== 0) {
                        event.accepted = false
                        return
                    }
                    console.log("TEXT_SEND_UI_RETURN")
                    var message=input.text.trim()
                    console.log("TEXT_SEND_TEXT_LENGTH chars=" + message.length)
                    if (message.length > 0) console.log("TEXT_SEND_BRIDGE_CALL")
                    if (message.length > 0 && coreBridge.sendMessage(message)) {
                        input.text=""
                        root.releaseComposerFocus()
                        bridge.setWorkspace("talk")
                    }
                    event.accepted = true
                }
            }

            Text {
                visible: !root.writing
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                text: runtimeMode === "native"
                      ? (voiceBridge ? ("Conversation locale prête · " + voiceBridge.statusText) : "Conversation locale prête")
                      : (coreBridge.interactionReady ? "Entrée pour envoyer · maintenir le micro pour parler" : "Interaction activée lorsque le Runtime est prêt.")
                color: root.lightMode ? "#6B8492" : "#4E7083"
                font.pixelSize: 6
            }
        }

        Rectangle {
            width: 34; height: 34; radius: 10
            anchors.verticalCenter: parent.verticalCenter
            color: (runtimeMode === "native" && voiceBridge && voiceBridge.state === "listening")
                   ? (root.lightMode ? "#B8E8F7" : "#365AD9FF")
                   : (root.lightMode ? "#F7FFFFFF" : "#82071320")
            border.width: 1
            border.color: root.lightMode ? "#4D2F84A7" : "#3274EFFF"

            Canvas {
                anchors.centerIn: parent
                width: 16; height: 16
                antialiasing: true
                renderTarget: Canvas.FramebufferObject
                onPaint: {
                    var c = getContext("2d")
                    c.clearRect(0, 0, width, height)
                    c.strokeStyle = root.lightMode ? "#15516A" : "#8AE8F7"
                    c.fillStyle = root.lightMode ? "#15516A" : "#8AE8F7"
                    c.lineWidth = 1.45
                    c.lineCap = "round"
                    c.lineJoin = "round"

                    c.beginPath()
                    c.moveTo(8, 2.2)
                    c.bezierCurveTo(10.2, 2.2, 11.3, 3.7, 11.3, 5.6)
                    c.lineTo(11.3, 8.2)
                    c.bezierCurveTo(11.3, 10.2, 10.2, 11.7, 8, 11.7)
                    c.bezierCurveTo(5.8, 11.7, 4.7, 10.2, 4.7, 8.2)
                    c.lineTo(4.7, 5.6)
                    c.bezierCurveTo(4.7, 3.7, 5.8, 2.2, 8, 2.2)
                    c.closePath()
                    c.stroke()

                    c.beginPath()
                    c.moveTo(2.8, 7.8)
                    c.lineTo(2.8, 8.4)
                    c.bezierCurveTo(2.8, 11.4, 5.0, 13.5, 8.0, 13.5)
                    c.bezierCurveTo(11.0, 13.5, 13.2, 11.4, 13.2, 8.4)
                    c.lineTo(13.2, 7.8)
                    c.stroke()

                    c.beginPath()
                    c.moveTo(8, 13.6)
                    c.lineTo(8, 15.4)
                    c.stroke()

                    c.beginPath()
                    c.moveTo(5.5, 15.4)
                    c.lineTo(10.5, 15.4)
                    c.stroke()
                }
            }

            MouseArea {
                anchors.fill: parent
                preventStealing: true
                enabled: runtimeMode === "native"
                         ? voiceBridge && voiceBridge.available
                           && (voiceBridge.state === "idle" || voiceBridge.state === "listening" || voiceBridge.state === "speaking")
                         : (coreBridge.connected && coreBridge.interactionReady)
                onPressed: {
                    if (runtimeMode === "native") {
                        if (voiceBridge.state === "speaking") {
                            voiceBridge.stopSpeaking()
                        } else if (voiceBridge.state === "idle") {
                            voiceBridge.diagnosticTrace("PTT_QML_PRESS")
                            voiceBridge.startListening()
                        }
                    } else {
                        coreBridge.micStart()
                    }
                }
                onReleased: {
                    if (runtimeMode === "native") {
                        voiceBridge.diagnosticTrace("PTT_QML_RELEASE")
                        voiceBridge.stopListening()
                    } else {
                        coreBridge.micStop()
                    }
                }
                onCanceled: {
                    if (runtimeMode === "native" && voiceBridge) {
                        voiceBridge.diagnosticTrace("PTT_QML_CANCEL")
                        voiceBridge.cancel()
                    }
                    else if (runtimeMode !== "native") coreBridge.micStop()
                }
            }
        }

        Rectangle {
            width: 34; height: 34; radius: 10
            anchors.verticalCenter: parent.verticalCenter
            color: root.lightMode ? "#F7FFFFFF" : "#82071320"
            border.width: 1
            border.color: root.lightMode ? "#4D2F84A7" : "#326B87FF"

            Canvas {
                anchors.centerIn: parent
                width: 16; height: 16
                visible: !coreBridge.canCancel
                antialiasing: true
                renderTarget: Canvas.FramebufferObject
                onPaint: {
                    var c = getContext("2d")
                    c.clearRect(0, 0, width, height)
                    c.strokeStyle = root.lightMode ? "#086F8E" : "#75DCFF"
                    c.fillStyle = root.lightMode ? "#086F8E" : "#75DCFF"
                    c.lineWidth = 1.4
                    c.lineCap = "round"
                    c.lineJoin = "round"

                    c.beginPath()
                    c.moveTo(2.2, 7.9)
                    c.lineTo(13.3, 2.5)
                    c.lineTo(9.2, 13.8)
                    c.lineTo(7.5, 9.6)
                    c.lineTo(2.2, 7.9)
                    c.closePath()
                    c.stroke()

                    c.beginPath()
                    c.moveTo(7.6, 9.5)
                    c.lineTo(13.2, 2.6)
                    c.stroke()
                }
            }

            Text {
                anchors.centerIn: parent
                visible: coreBridge.canCancel
                text: "STOP"
                color: root.lightMode ? "#086F8E" : "#75DCFF"
                font.pixelSize: 8
                font.weight: Font.DemiBold
            }

            TapHandler {
                enabled: coreBridge.canCancel || root.textSubmissionReady
                onTapped: {
                    if (coreBridge.canCancel) {
                        coreBridge.cancelAgent(coreBridge.activeRequestId)
                        return
                    }
                    console.log("TEXT_SEND_UI_CLICK")
                    var message=input.text.trim()
                    console.log("TEXT_SEND_TEXT_LENGTH chars=" + message.length)
                    if (message.length > 0) console.log("TEXT_SEND_BRIDGE_CALL")
                    if (message.length > 0 && coreBridge.sendMessage(message)) {
                        input.text=""
                        root.releaseComposerFocus()
                        bridge.setWorkspace("talk")
                    }
                }
            }
        }
    }

}

