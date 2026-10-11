import QtQuick
Rectangle {
    id: root
    property bool lightMode: false
    property real dockSafeWidth: 0
    property real outerMargin: 12
    radius: 20
    color: lightMode ? "#F2F8FA" : "#E90A1420"
    border.width: 1
    border.color: lightMode ? "#4A7890" : "#327A9DB2"
    clip: true
}
