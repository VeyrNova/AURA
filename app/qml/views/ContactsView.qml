import QtQuick
import QtQuick.Controls

Item {
 id: root; property bool lightMode: false
 readonly property color bg: lightMode ? "#EAF4F7" : "#07131E"
 readonly property color card: lightMode ? "#F4FAFC" : "#0A202D"
 readonly property color fg: lightMode ? "#17394D" : "#D8F7FF"
 readonly property color muted: lightMode ? "#557487" : "#84A8B7"
 readonly property color accent: lightMode ? "#2299A8" : "#74EFFF"
 Component.onCompleted: contactsBridge.refresh()
 Rectangle { anchors.fill: parent; radius: 16; color: root.bg; border.color: root.accent; border.width: 1
  Column { anchors.fill: parent; anchors.margins: 24; spacing: 14
   Row { width: parent.width; height: 38; spacing: 12
    Text { text: "CONTACTS"; color: root.fg; font.pixelSize: 22; font.letterSpacing: 2; anchors.verticalCenter: parent.verticalCenter }
    Item { width: 1; height: 1 }
    TextField { id: search; width: Math.max(180,parent.width-330); height: 36; placeholderText: "Rechercher"; onAccepted: contactsBridge.search(text); color: root.fg; placeholderTextColor: root.muted }
    Button { text: "NOUVEAU CONTACT"; onClicked: { contactsBridge.cancelPending(); contactsBridge.selectContact("") } }
   }
   Row { width: parent.width; height: parent.height-66; spacing: 14
    Rectangle { width: Math.max(280,parent.width*.38); height: parent.height; color: root.card; radius: 12
     ListView { id: list; anchors.fill: parent; anchors.margins: 8; clip: true; model: contactsBridge.items; spacing: 6
      delegate: Rectangle { required property var modelData; width: list.width; height: 68; radius: 9; color: contactsBridge.selected.contact_id===modelData.contact_id ? root.accent : "transparent"
       Text { anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter; text: modelData.display_name; color: contactsBridge.selected.contact_id===modelData.contact_id ? root.bg : root.fg; font.pixelSize: 14 }
       Text { anchors.left: parent.left; anchors.leftMargin: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; text: modelData.organization || (modelData.emails.length ? modelData.emails[0] : ""); color: root.muted; font.pixelSize: 10 }
       MouseArea { anchors.fill: parent; onClicked: contactsBridge.selectContact(modelData.contact_id) }
      }
      Text { anchors.centerIn: parent; visible: contactsBridge.items.length===0; text: "Aucun contact"; color: root.muted }
     }
    }
    Rectangle { width: Math.max(300,parent.width*.62); height: parent.height; color: root.card; radius: 12
     Column { anchors.fill: parent; anchors.margins: 18; spacing: 10
      Text { text: contactsBridge.selected.display_name || "Nouveau contact"; color: root.fg; font.pixelSize: 18 }
      TextField { id: name; width: parent.width; placeholderText: "Nom"; text: contactsBridge.selected.display_name || "" }
      TextField { id: org; width: parent.width; placeholderText: "Organisation"; text: contactsBridge.selected.organization || "" }
      TextField { id: emails; width: parent.width; placeholderText: "Emails (séparés par des virgules)"; text: (contactsBridge.selected.emails || []).join(", ") }
      TextField { id: phones; width: parent.width; placeholderText: "Téléphones (séparés par des virgules)"; text: (contactsBridge.selected.phones || []).join(", ") }
      TextArea { id: notes; width: parent.width; height: 90; placeholderText: "Notes"; text: contactsBridge.selected.notes || ""; wrapMode: TextEdit.Wrap }
      Row { spacing: 10
       Button { text: "ANNULER"; onClicked: contactsBridge.cancelPending() }
       Button { text: "ENREGISTRER"; onClicked: contactsBridge.selected.contact_id ? contactsBridge.updateContact(contactsBridge.selected.contact_id,name.text,emails.text,phones.text,org.text,notes.text,contactsBridge.selected.version||1) : contactsBridge.createContact(name.text,emails.text,phones.text,org.text,notes.text) }
       Button { visible: !!contactsBridge.selected.contact_id; text: "SUPPRIMER"; onClicked: contactsBridge.requestDelete(contactsBridge.selected.contact_id,contactsBridge.selected.display_name) }
      }
      Text { text: contactsBridge.errorCode; color: "#E98282"; visible: text.length>0 }
     }
    }
   }
  }
 }
 Dialog { id: confirm; modal: true; width: 420; title: "Supprimer ce contact ?"; standardButtons: Dialog.Ok|Dialog.Cancel; onAccepted: contactsBridge.confirmDelete(); onRejected: contactsBridge.cancelPending(); visible: contactsBridge.pendingAction.kind === "delete"; contentItem: Text { width: 380; text: "La suppression de « " + contactsBridge.pendingAction.displayName + " » est définitive."; color: root.fg; padding: 20; wrapMode: Text.Wrap }
 }
 Connections { target: contactsBridge; function onChanged() { if (contactsBridge.pendingAction.kind !== "delete") confirm.close(); else confirm.open() } }
}
