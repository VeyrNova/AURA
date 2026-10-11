import QtQuick
import QtQuick.Controls

Rectangle {
    // nativeCore.confirmPendingAction()/nativeCore.cancelPendingAction() remain bridge compatibility
    // slots; this surface always calls the ID-bound slots below.
    id: root
    property var nativeCore: coreBridge
    property bool lightMode: false
    visible: nativeCore.hasPendingAction && nativeCore.pendingActionState !== "error" && nativeCore.pendingActionState !== "expired"
    width: Math.min(parent ? parent.width - 32 : 520, 520)
    implicitHeight: content.implicitHeight + 32
    radius: 18
    color: lightMode ? "#EAF7F8E8" : "#0C2533E8"
    border.width: 1
    border.color: lightMode ? "#669DB0" : "#277A91"
    opacity: visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 160 } }

    Column {
        id: content
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top; anchors.margins: 16
        spacing: 9
        Text { text: "AURA · CONFIRMATION REQUISE"; color: lightMode ? "#176C7A" : "#74EFFF"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1.2 }
        Text { width: parent.width; text: nativeCore.pendingActionSummary; color: lightMode ? "#17394D" : "#D8F7FF"; wrapMode: Text.Wrap; font.pixelSize: 14 }
        Text { visible: nativeCore.pendingActionState === "confirmed"; text: "Exécution…"; color: lightMode ? "#557487" : "#84A8B7"; font.pixelSize: 11 }
        Text { visible: nativeCore.pendingActionError.length > 0; text: "Impossible d’exécuter cette action."; color: lightMode ? "#9A4B5B" : "#FF9BAF"; wrapMode: Text.Wrap; font.pixelSize: 11 }
        Row { spacing: 10
            Rectangle { id: cancelButton; width: 112; height: 36; radius: 11; property bool active: nativeCore.pendingActionState !== "confirmed"; color: !active ? (lightMode ? "#D7E1E4" : "#172A33") : (cancelTap.pressed ? (lightMode ? "#C4DCE1" : "#143846") : (cancelTap.containsMouse ? (lightMode ? "#DDEEF1" : "#12303D") : (lightMode ? "#D3E7EA" : "#102631"))); border.width: 1; border.color: lightMode ? "#6E9AA5" : "#356B7C"
                Text { anchors.centerIn: parent; text: "ANNULER"; color: parent.active ? (lightMode ? "#28566A" : "#B8DDE6") : (lightMode ? "#8AA0A6" : "#6E858D"); font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                MouseArea { id: cancelTap; anchors.fill: parent; enabled: parent.active; hoverEnabled: true; onClicked: nativeCore.cancelPreparedAction(nativeCore.pendingActionId) }
            }
            Rectangle { id: confirmButton; width: 128; height: 36; radius: 11; property bool active: nativeCore.pendingActionState !== "confirmed"; color: !active ? (lightMode ? "#B8D5D9" : "#214651") : (confirmTap.pressed ? (lightMode ? "#42B9C4" : "#167A91") : (confirmTap.containsMouse ? (lightMode ? "#68D4DA" : "#259AB0") : (lightMode ? "#2FAAB5" : "#176F84"))); border.width: 1; border.color: lightMode ? "#197D89" : "#6EEFFF"
                Text { anchors.centerIn: parent; text: "CONFIRMER"; color: parent.active ? "#F4FEFF" : (lightMode ? "#6D858A" : "#8EAEB4"); font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                MouseArea { id: confirmTap; anchors.fill: parent; enabled: parent.active; hoverEnabled: true; onClicked: nativeCore.confirmPreparedAction(nativeCore.pendingActionId) }
            }
        }
    }
}
