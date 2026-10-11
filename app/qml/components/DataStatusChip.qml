import QtQuick

Rectangle {
    id: root
    property bool lightMode: false

    visible: coreBridge.dataStatus.length > 0
    implicitWidth: Math.max(130, statusText.implicitWidth + 30)
    implicitHeight: 30
    radius: 9
    color: coreBridge.dataStatusOk
           ? (lightMode ? "#DDF5FCF8" : "#80102A2A")
           : (lightMode ? "#EFFFF2F4" : "#8A260B18")
    border.width: 1
    border.color: coreBridge.dataStatusOk ? "#4964D9C3" : "#65FF6F94"

    Text {
        id: statusText
        anchors.centerIn: parent
        text: coreBridge.dataStatus
        color: coreBridge.dataStatusOk
               ? (root.lightMode ? "#277364" : "#73E7C8")
               : (root.lightMode ? "#8A3145" : "#FF8FA9")
        font.pixelSize: 8
        font.letterSpacing: 0.5
    }

    TapHandler {
        onTapped: coreBridge.clearDataStatus()
    }
}
