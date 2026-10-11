import QtQuick
Item {
    id: root
    property alias text: input.text
    property string placeholderText: ""
    property bool lightMode: false
    Rectangle { anchors.fill: parent; radius: 10; color: lightMode ? "#EAF7FA" : "#32132636"; border.width: 1; border.color: input.activeFocus ? "#55D9F5" : "#3B7890A0" }
    TextEdit { id: input; anchors.fill: parent; anchors.margins: 10; wrapMode: TextEdit.Wrap; color: lightMode ? "#17394D" : "#D7F5FF"; font.pixelSize: 11 }
    Text { visible: input.text.length === 0 && !input.activeFocus; anchors.left: input.left; anchors.top: input.top; text: root.placeholderText; color: lightMode ? "#78909C" : "#6E8997"; font.pixelSize: 10 }
}
