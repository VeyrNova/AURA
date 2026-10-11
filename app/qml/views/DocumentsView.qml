import QtQuick
import QtQuick.Controls

Item {
    id: root; property bool lightMode: false
    readonly property color panel: lightMode ? "#EAF4F7" : "#06111B"
    readonly property color card: lightMode ? "#F7FCFD" : "#0A1B28"
    readonly property color text0: lightMode ? "#17394D" : "#E5FAFF"
    readonly property color text1: lightMode ? "#587789" : "#83A8B9"
    readonly property color accent: lightMode ? "#278FA4" : "#74EFFF"
    Rectangle { anchors.fill: parent; radius: 16; color: root.panel; border.width: 1; border.color: root.lightMode ? "#557E91" : "#1F6680" }
    Column { anchors.fill: parent; anchors.margins: 24; spacing: 12
        Text { text: "DOCUMENTS"; color: root.text0; font.pixelSize: 23; font.weight: Font.DemiBold; font.letterSpacing: 2.4 }
        Text { width: parent.width; text: "DOCUMENTS" + (documentsBridge.currentPath ? "  ›  " + documentsBridge.currentPath.split("/").join("  ›  ") : ""); elide: Text.ElideMiddle; color: root.text1; font.pixelSize: 10; Accessible.name: text }
        Row { width: parent.width; height: 40; spacing: 8
            TextField { id: searchBox; width: Math.max(220,parent.width-390); height: 40; placeholderText: "Rechercher un fichier"; color: root.text0; Accessible.name: "Recherche documents"; onAccepted: documentsBridge.search(text) }
            Button { text: "RECHERCHER"; onClicked: documentsBridge.search(searchBox.text) }
            Button { text: "NOUVEAU FICHIER"; onClicked: createFileDialog.open() }
            Button { text: "NOUVEAU DOSSIER"; onClicked: createFolderDialog.open() }
            Button { text: "↻"; onClicked: documentsBridge.listDirectory(documentsBridge.currentPath) }
        }
        SplitView { width: parent.width; height: Math.max(180,parent.height-120); orientation: Qt.Horizontal
            Rectangle { SplitView.minimumWidth: 360; SplitView.preferredWidth: parent.width*.53; color: "transparent"
                ListView { id: fileList; anchors.fill: parent; clip: true; spacing: 7; model: documentsBridge.items; ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle { required property var modelData; width: fileList.width; height: 58; radius: 10; color: root.card; border.width: 1; border.color: rowHover.hovered ? root.accent : "#284F63"
                        Text { anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter; text: modelData.kind === "folder" ? "▱" : "▤"; color: root.accent; font.pixelSize: 18 }
                        Column { anchors.left: parent.left; anchors.leftMargin: 48; anchors.right: actions.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                        Text { width: parent.width; text: modelData.name; elide: Text.ElideMiddle; color: root.text0; font.pixelSize: 12; font.weight: Font.DemiBold; Accessible.name: "Résultat document " + modelData.name }
                            Text { text: modelData.kind === "folder" ? "DOSSIER" : (modelData.extension.toUpperCase()+" · "+modelData.size+" octets"); color: root.text1; font.pixelSize: 8 }
                        }
                        Row { id: actions; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            Button { text: modelData.kind === "folder" ? "OUVRIR" : "LIRE"; onClicked: modelData.kind === "folder" ? documentsBridge.listDirectory(modelData.path) : documentsBridge.openItem(modelData.path) }
                            Button { text: "⋯"; onClicked: { actionMenu.itemPath=modelData.path; actionMenu.itemName=modelData.name; actionMenu.isFolder=modelData.kind==="folder"; actionMenu.popup() } }
                        }
                        HoverHandler { id: rowHover }
                    }
                    Text { anchors.centerIn: parent; visible: documentsBridge.state === "empty"; text: searchBox.text ? "Aucun résultat" : "Dossier vide"; color: root.text1 }
                }
            }
            Rectangle { SplitView.minimumWidth: 300; SplitView.fillWidth: true; color: root.card; radius: 12; border.width: 1; border.color: "#284F63"
                Column { anchors.fill: parent; anchors.margins: 12; spacing: 9
                    Text { width: parent.width; text: documentsBridge.openedIdentity || "APERÇU"; elide: Text.ElideMiddle; color: root.text0; font.pixelSize: 11; font.weight: Font.DemiBold; Accessible.name: "Document ouvert " + text }
                    TextArea { id: editor; width: parent.width; height: Math.max(100,parent.height-82); visible: !documentsBridge.document.binary; text: documentsBridge.document.content || ""; color: root.text0; wrapMode: TextEdit.Wrap; onTextChanged: if(activeFocus) documentsBridge.setEditorText(text) }
                    Text { visible: documentsBridge.document.binary === true; width: parent.width; wrapMode: Text.WordWrap; text: documentsBridge.errorCode === "FILE_TOO_LARGE" ? "FICHIER TROP VOLUMINEUX" : "Format binaire · utilisez l’application système"; color: root.text1 }
                    Row {
                        spacing: 8
                        Button { text: documentsBridge.dirty ? "ENREGISTRER *" : "ENREGISTRER"; enabled: documentsBridge.dirty; onClicked: documentsBridge.saveDocument(false) }
                        Button { text: "OUVRIR EXTERNE"; enabled: !!documentsBridge.document.path; onClicked: documentsBridge.openExternal(documentsBridge.document.path) }
                    }
                }
            }
        }
        Text { visible: documentsBridge.state === "loading" || documentsBridge.state === "error"; text: documentsBridge.state === "loading" ? "Chargement…" : documentsBridge.errorCode; color: documentsBridge.state === "error" ? "#FF9EAA" : root.text1 }
    }
    Menu { id: actionMenu; property string itemPath; property string itemName; property bool isFolder
        MenuItem { text: "Ouvrir avec l’application système"; onTriggered: documentsBridge.openExternal(actionMenu.itemPath) }
        MenuItem { text: "Renommer / déplacer"; onTriggered: { moveSource.text=actionMenu.itemPath; moveDestination.text=actionMenu.itemPath; moveDialog.open() } }
        MenuItem { text: "Supprimer"; onTriggered: documentsBridge.requestDelete(actionMenu.itemPath,actionMenu.itemName,actionMenu.isFolder) }
    }
    Dialog { id: createFileDialog; title: "Nouveau fichier texte"; modal: true; standardButtons: Dialog.Ok|Dialog.Cancel; anchors.centerIn: parent; onAccepted: documentsBridge.createText(documentsBridge.currentPath,newFileName.text,""); TextField { id:newFileName; placeholderText:"notes.txt" } }
    Dialog { id: createFolderDialog; title: "Nouveau dossier"; modal: true; standardButtons: Dialog.Ok|Dialog.Cancel; anchors.centerIn: parent; onAccepted: documentsBridge.createFolder(documentsBridge.currentPath,newFolderName.text); TextField { id:newFolderName; placeholderText:"Nom du dossier" } }
    Dialog { id: moveDialog; title: "Renommer ou déplacer"; modal: true; standardButtons: Dialog.Ok|Dialog.Cancel; anchors.centerIn: parent; onAccepted: documentsBridge.moveItem(moveSource.text,moveDestination.text); Column { TextField{id:moveSource;visible:false} TextField{id:moveDestination;placeholderText:"Chemin relatif de destination"} } }
    Dialog { id: deleteDialog; title: "Confirmer la suppression définitive"; modal: true; visible: documentsBridge.pendingAction.kind === "delete"; standardButtons: Dialog.Yes|Dialog.Cancel; anchors.centerIn: parent; onAccepted: documentsBridge.confirmDelete(recursiveDelete.checked); onRejected: documentsBridge.cancelPending(); Column { spacing:8; Text { text:"Supprimer « "+(documentsBridge.pendingAction.name||"")+" » ?" } CheckBox { id:recursiveDelete; visible: documentsBridge.pendingAction.isFolder === true; text:"Je confirme la suppression si le dossier n’est pas vide" } } }
    Component.onCompleted: documentsBridge.listDirectory("")
}
