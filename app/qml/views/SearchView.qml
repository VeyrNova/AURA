import QtQuick
import QtQuick.Controls

Item {
    id: root
    property bool lightMode: false
    readonly property color panel: lightMode ? "#EAF4F7" : "#06111B"
    readonly property color card: lightMode ? "#F7FCFD" : "#0A1B28"
    readonly property color text0: lightMode ? "#17394D" : "#E5FAFF"
    readonly property color text1: lightMode ? "#587789" : "#83A8B9"
    readonly property color accent: lightMode ? "#278FA4" : "#74EFFF"

    Rectangle { anchors.fill: parent; radius: 16; color: root.panel; border.width: 1; border.color: root.lightMode ? "#557E91" : "#1F6680" }

    Column {
        anchors.fill: parent
        anchors.margins: 26
        spacing: 16

        Column {
            width: parent.width; spacing: 5
            Text { text: "RECHERCHE"; color: root.text0; font.pixelSize: 23; font.weight: Font.DemiBold; font.letterSpacing: 2.4 }
            Text { text: "WEB · RÉSULTATS SOURCÉS"; color: root.text1; font.pixelSize: 9; font.letterSpacing: 1.3 }
        }

        Row {
            width: parent.width; height: 46; spacing: 10
            Rectangle {
                width: parent.width - 132; height: parent.height; radius: 12; color: root.card; border.width: 1; border.color: searchInput.activeFocus ? root.accent : (root.lightMode ? "#658799" : "#24546A")
                TextField {
                    id: searchInput; objectName: "nativeSearchInput"
                    anchors.fill: parent; anchors.margins: 3
                    placeholderText: "Rechercher sur le Web"
                    color: root.text0; placeholderTextColor: root.text1
                    background: null; selectByMouse: true
                    onAccepted: searchBridge.search(text)
                }
            }
            Rectangle {
                width: 122; height: 46; radius: 12
                color: searchMouse.pressed ? "#4167D7E8" : searchMouse.containsMouse ? "#3265CCDE" : "#2560B9CB"
                border.width: 1; border.color: root.accent
                Text { anchors.centerIn: parent; text: searchBridge.loading ? "ANNULER" : "RECHERCHER"; color: root.text0; font.pixelSize: 10; font.weight: Font.DemiBold }
                MouseArea { id: searchMouse; anchors.fill: parent; hoverEnabled: true; onClicked: searchBridge.loading ? searchBridge.cancel() : searchBridge.search(searchInput.text) }
            }
        }

        Item {
            width: parent.width; height: Math.max(160, parent.height - 132)
            ListView {
                id: resultsList; objectName: "nativeSearchResults"
                anchors.fill: parent; clip: true; spacing: 10
                model: searchBridge.results
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    width: resultsList.width; height: Math.max(112, resultColumn.implicitHeight + 30)
                    radius: 13; color: root.card; border.width: 1; border.color: openHover.hovered ? root.accent : (root.lightMode ? "#64889A" : "#244B60")
                    Column {
                        id: resultColumn
                        anchors.left: parent.left; anchors.right: openAction.left; anchors.top: parent.top
                        anchors.margins: 15; anchors.rightMargin: 16; spacing: 7
                        Text { width: parent.width; text: modelData.title; color: root.text0; font.pixelSize: 14; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                        Text { width: parent.width; text: modelData.domain + " · " + modelData.provider; color: root.accent; font.pixelSize: 9; elide: Text.ElideRight }
                        Text { width: parent.width; text: modelData.snippet; color: root.text1; font.pixelSize: 11; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight }
                    }
                    Rectangle {
                        id: openAction; anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                        width: 82; height: 36; radius: 10; color: openHover.hovered ? "#2869CBDA" : "#17516A7A"; border.width: 1; border.color: root.accent
                        Text { anchors.centerIn: parent; text: "OUVRIR"; color: root.text0; font.pixelSize: 9; font.weight: Font.DemiBold }
                        HoverHandler { id: openHover }
                        TapHandler { onTapped: searchBridge.openResult(modelData.url) }
                    }
                }
            }

            Text {
                anchors.centerIn: parent; width: Math.min(parent.width - 40, 440); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                visible: searchBridge.state !== "ready"
                text: searchBridge.state === "loading" ? "Recherche en cours…"
                    : searchBridge.state === "empty" ? "Aucun résultat trouvé"
                    : searchBridge.state === "offline" ? "RÉSEAU INDISPONIBLE"
                    : searchBridge.state === "timeout" ? "Recherche expirée · vous pouvez relancer"
                    : searchBridge.state === "error" ? "La recherche est momentanément indisponible"
                    : "Recherchez le Web sans quitter l’interface AURA."
                color: searchBridge.state === "error" || searchBridge.state === "offline" || searchBridge.state === "timeout" ? "#FF9EAA" : root.text1
                font.pixelSize: 13
            }
        }
    }
}
