import QtQuick
Rectangle {
    id: root
    property string text: ""
    property bool lightMode: false
    property string variant: "secondary"
    signal clicked()
    height: 32; radius: 9
    color: variant === "danger" ? (lightMode ? "#F7D8DE" : "#713344") : (variant === "primary" ? (lightMode ? "#BDEEF5" : "#276D86") : (lightMode ? "#EAF7FA" : "#32132636"))
    border.width: 1; border.color: variant === "primary" ? "#55D9F5" : "#3B7890A0"
    Text { anchors.centerIn: parent; text: root.text; color: lightMode ? "#17394D" : "#D7F5FF"; font.pixelSize: 9; font.bold: true }
    MouseArea { anchors.fill: parent; onClicked: root.clicked() }
}
