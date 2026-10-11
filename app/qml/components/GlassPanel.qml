import QtQuick

Rectangle {
    id: root
    property bool lightMode: false
    property color accent: "#74EFFF"
    radius: 18
    border.width: 1
    border.color: lightMode ? "#467A9CB3" : "#2E73E4FF"
    gradient: Gradient {
        GradientStop { position: 0.0; color: root.lightMode ? "#F7FFFFFF" : "#C9071422" }
        GradientStop { position: 0.55; color: root.lightMode ? "#EBF6FAFD" : "#AF05101C" }
        GradientStop { position: 1.0; color: root.lightMode ? "#DDEAF4F9" : "#98030B14" }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: Math.max(0,parent.radius-1)
        color: "transparent"
        border.width: 1
        border.color: root.lightMode ? "#7AFFFFFF" : "#12FFFFFF"
        opacity: .58
    }
    Rectangle {
        width: parent.width*.58; height: 1
        anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
        color: root.accent; opacity: .34
    }
}
