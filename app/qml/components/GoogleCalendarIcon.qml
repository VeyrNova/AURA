import QtQuick

// Local, dependency-free Google Calendar identity mark.  The repository has
// no dedicated Calendar asset; this keeps event chips free of the generic G.
Rectangle {
    id: icon
    property color accent: "#6ED7F4"
    width: 16
    height: 16
    radius: 4
    color: "#172E43"
    border.width: 1
    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.8)
    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 4; radius: 2; color: accent }
    Text { anchors.centerIn: parent; anchors.verticalCenterOffset: 2; text: "31"; color: "#DDF9FF"; font.pixelSize: 6; font.weight: Font.DemiBold }
}
