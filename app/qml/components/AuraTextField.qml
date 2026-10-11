import QtQuick
Item {
    id: root
    property alias text: input.text
    property string placeholderText: ""
    property bool passwordMode: false
    property bool lightMode: false
    property int fieldHeight: 32
    signal editingFinished()
    implicitHeight: fieldHeight
    implicitWidth: 180
    Rectangle { anchors.fill: parent; radius: 9; color: root.lightMode ? "#EAF7FA" : "#32132636"; border.width: 1; border.color: input.activeFocus ? "#55D9F5" : (root.lightMode ? "#4A7890" : "#3B7890A0") }
    TextInput { id: input; anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; verticalAlignment: TextInput.AlignVCenter; color: root.lightMode ? "#17394D" : "#D7F5FF"; selectionColor: "#397F9A"; font.pixelSize: 11; echoMode: root.passwordMode ? TextInput.Password : TextInput.Normal; onEditingFinished: root.editingFinished() }
    Text { visible: input.text.length === 0 && !input.activeFocus; anchors.left: input.left; anchors.verticalCenter: input.verticalCenter; text: root.placeholderText; color: root.lightMode ? "#78909C" : "#6E8997"; font.pixelSize: 10 }
}
