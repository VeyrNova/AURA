import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    property bool lightMode: false
    readonly property color surface: lightMode ? "#EDF7F9" : "#081923"
    readonly property color card: lightMode ? "#FFFFFF" : "#102532"
    readonly property color ink: lightMode ? "#17394D" : "#D8F7FF"
    readonly property color muted: lightMode ? "#557487" : "#91ADBC"
    readonly property color violet: lightMode ? "#7868C7" : "#A58BFF"
    readonly property bool permissionRequired: mailBridge.permissionState === "permission_required" || mailBridge.state === "PERMISSION_REQUIRED"
    onVisibleChanged: if (visible && !permissionRequired && mailBridge.messages.length === 0) mailBridge.openInbox()
    Component.onCompleted: if (!permissionRequired && mailBridge.messages.length === 0 && !mailBridge.loading) mailBridge.openInbox()

    Rectangle { anchors.fill: parent; color: root.surface; radius: 18; border.width: 1; border.color: "#2E7897A8" }
    Column {
        anchors.fill: parent; anchors.margins: 18; spacing: 12
        Row {
            width: parent.width; height: 42; spacing: 10
            Column { width: Math.max(160, parent.width - 500); spacing: 2; Text { text: "GOOGLE MAIL"; color: root.ink; font.pixelSize: 18; font.weight: Font.DemiBold; font.letterSpacing: 1.2 } Text { text: root.permissionRequired ? "AUTORISATION REQUISE" : "AURA MAIL CENTER · LECTURE SEULE"; color: root.permissionRequired ? "#E6B86A" : root.muted; font.pixelSize: 8; font.letterSpacing: 1 } }
            Rectangle {
                width: Math.min(220, parent.width * .27); height: 38; radius: 11
                color: root.card; border.width: 1; border.color: "#3974DDEA"
                TextField {
                    id: query; objectName: "nativeMailSearch"; anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 8
                    placeholderText: "Rechercher dans les mails"; color: root.ink; placeholderTextColor: root.muted
                    font.pixelSize: 10; background: null; onAccepted: if (!root.permissionRequired) mailBridge.search(text)
                }
            }
            AuraButton { objectName: "nativeMailSync"; width: 90; height: 38; lightMode: root.lightMode; text: mailBridge.loading ? "SYNCHRO…" : "ACTUALISER"; enabled: !mailBridge.loading; onClicked: if (!root.permissionRequired) mailBridge.refresh() }
            Text { objectName: "nativeMailReadOnlyStatus"; width: 160; elide: Text.ElideNone; text: root.permissionRequired ? "● AUTORISATION REQUISE" : "● CONNECTÉ · LECTURE SEULE"; color: root.permissionRequired ? "#E6B86A" : "#77E5BE"; font.pixelSize: 8; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            width: parent.width; height: Math.max(200, parent.height - 76); spacing: 10
            Rectangle {
                id: sidebar; objectName: "nativeMailSidebar"; width: Math.max(136, Math.min(176, parent.width * .18)); height: parent.height
                radius: 14; color: root.card; border.width: 1; border.color: "#3475A9B8"
                Column { anchors.fill: parent; anchors.margins: 12; spacing: 8
                    Text { text: "BOÎTES"; color: root.muted; font.pixelSize: 9; font.weight: Font.DemiBold }
                    Repeater { model: [
                        {key:"inbox",label:"Boîte de réception"}, {key:"unread",label:"Non lus"},
                        {key:"search",label:"Recherche"}, {key:"draft",label:"Brouillons"}, {key:"send",label:"Envoyer"}]
                        delegate: Rectangle { width: parent.width; height: 34; radius: 10; opacity: (modelData.key === "draft" || modelData.key === "send") && mailBridge.readOnly ? .46 : 1; color: mailBridge.mode === modelData.key ? "#345E87A0" : "transparent"; border.width: mailBridge.mode === modelData.key ? 1 : 0; border.color: "#4D9DEBFF"
                            Text { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: ["▣","●","⌕","□","↗"][index]; color: mailBridge.mode === modelData.key ? "#75EEFF" : root.muted; font.pixelSize: 13 }
                        Text { anchors.left: parent.left; anchors.leftMargin: 30; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 38; elide: Text.ElideRight; text: modelData.label + (modelData.key === "unread" ? (mailBridge.loading ? "  ···" : "  " + mailBridge.unreadCount) : ""); color: root.ink; font.pixelSize: 10; font.weight: mailBridge.mode === modelData.key ? Font.DemiBold : Font.Normal }
                            Text { visible: (modelData.key === "draft" || modelData.key === "send") && mailBridge.readOnly; anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: "⌑"; color: root.muted; font.pixelSize: 11 }
                            TapHandler { enabled: !((modelData.key === "draft" || modelData.key === "send") && mailBridge.readOnly); onTapped: { mailBridge.setMode(modelData.key); if (modelData.key === "search") query.forceActiveFocus() } }
                        }
                    }
                    Rectangle { objectName: "nativeMailStatusCard"; width: parent.width; height: 82; radius: 12; color: root.lightMode ? "#DCECF0" : "#0D202D"; border.width: 1; border.color: "#3C7895A8"
                        Column { anchors.fill: parent; anchors.margins: 9; spacing: 4; Text { text: "GOOGLE WORKSPACE"; color: root.muted; font.pixelSize: 8; font.letterSpacing: 1 } Text { text: root.permissionRequired ? "● Autorisation Gmail requise" : "● Compte connecté"; color: root.permissionRequired ? "#E6B86A" : "#77E5BE"; font.pixelSize: 9 } Text { text: "Mode : Lecture seule"; color: root.muted; font.pixelSize: 8 } }
                    }
                }
            }
            Rectangle {
                id: center; objectName: "nativeMailListPanel"; width: Math.max(220, parent.width * .43); height: parent.height
                radius: 14; color: root.card; border.width: 1; border.color: "#3475A9B8"
                Column { anchors.fill: parent; anchors.margins: 12; spacing: 10
                    Row { width: parent.width; spacing: 8; Text { text: mailBridge.mode === "search" ? "RÉSULTATS DE RECHERCHE" : "BOÎTE DE RÉCEPTION"; color: root.ink; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: .6 } Text { text: mailBridge.messages.length ? mailBridge.messages.length + " messages" : ""; color: root.muted; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter } }
                    Row { width: parent.width; spacing: 5; Repeater { model: ["TOUS", "NON LUS", "AVEC PIÈCES JOINTES"]; delegate: Rectangle { width: index === 2 ? 126 : 72; height: 24; radius: 8; color: index === 0 ? "#2E6387A0" : "transparent"; border.width: 1; border.color: "#346D8CA0"; Text { anchors.centerIn: parent; text: modelData; color: root.muted; font.pixelSize: 7; font.letterSpacing: .5 } } } }
                    Rectangle { objectName: "nativeMailPermissionPanel"; visible: root.permissionRequired; width: parent.width; height: visible ? 174 : 0; radius: 12; color: root.lightMode ? "#E7F2F5" : "#112D3B"; border.width: 1; border.color: "#4C8CA6B4"
                        Column { anchors.fill: parent; anchors.margins: 14; spacing: 10
                            Text { text: "AUTORISATION GMAIL REQUISE"; color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Text { width: parent.width; wrapMode: Text.WordWrap; text: "AURA est prête à lire votre messagerie, mais votre compte Google doit autoriser l’accès Gmail en lecture seule."; color: root.muted; font.pixelSize: 10 }
                            AuraButton { width: 170; height: 36; lightMode: root.lightMode; variant: "primary"; text: "RÉAUTORISER GOOGLE"; onClicked: if (typeof coreBridge !== "undefined") coreBridge.startGoogleWorkspaceOAuth() }
                        }
                    }
                    Text { visible: mailBridge.mode === "draft" || mailBridge.mode === "send"; width: parent.width; wrapMode: Text.WordWrap; text: "Cette action est indisponible avec l’accès Gmail en lecture seule."; color: root.muted; font.pixelSize: 11 }
                    Column { objectName: "nativeMailSkeletons"; visible: mailBridge.loading && !root.permissionRequired; width: parent.width; spacing: 7; Repeater { model: 5; delegate: Rectangle { width: parent.width; height: 70; radius: 12; color: root.lightMode ? "#DDECEF" : "#122B38"; border.width: 1; border.color: "#244D5D"; Rectangle { x: 12; y: 17; width: 30; height: 30; radius: 15; color: root.lightMode ? "#C7DDE2" : "#1A3C4A" } Rectangle { x: 54; y: 16; width: parent.width*.42; height: 8; radius: 4; color: root.lightMode ? "#C7DDE2" : "#1A3C4A" } Rectangle { x: 54; y: 32; width: parent.width*.68; height: 7; radius: 4; color: root.lightMode ? "#C7DDE2" : "#1A3C4A" } Rectangle { x: 54; y: 47; width: parent.width*.52; height: 6; radius: 3; color: root.lightMode ? "#C7DDE2" : "#1A3C4A" } } } }
                    ListView { id: list; objectName: "nativeMailList"; visible: !mailBridge.loading; width: parent.width; height: Math.max(0, parent.height - 44 - (root.permissionRequired ? 184 : 0)); clip: true; spacing: 6
                        model: root.permissionRequired ? [] : mailBridge.messages
                        delegate: Rectangle { width: list.width; height: 82; radius: 12; color: mailBridge.selectedMessage.message_id === modelData.message_id ? (root.lightMode ? "#DDEDF5" : "#21465A") : (root.lightMode ? "#E6F0F3" : "#132E3C"); border.width: mailBridge.selectedMessage.message_id === modelData.message_id ? 1 : 1; border.color: mailBridge.selectedMessage.message_id === modelData.message_id ? "#62DDF5" : (modelData.unread ? "#377D91" : "#1B3B4A"); Rectangle { visible: modelData.unread || mailBridge.selectedMessage.message_id === modelData.message_id; width: 3; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; radius: 2; color: mailBridge.selectedMessage.message_id === modelData.message_id ? "#B094FF" : "#67E8FA" }
                            Rectangle { x: 10; y: 13; width: 32; height: 32; radius: 16; color: "#2A7593A8"; Text { anchors.centerIn: parent; text: (modelData.sender || "?").charAt(0).toUpperCase(); color: "#B9F5FF"; font.pixelSize: 13; font.weight: Font.DemiBold } }
                            Column { anchors.left: parent.left; anchors.leftMargin: 52; anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: 10; spacing: 4
                                Text { width: parent.width; text: modelData.sender || "Expéditeur inconnu"; color: root.ink; elide: Text.ElideRight; font.pixelSize: 10; font.weight: modelData.unread ? Font.DemiBold : Font.Normal }
                                Text { width: parent.width; text: (modelData.subject || "Sans objet") + (modelData.attachments && modelData.attachments.length ? "  ·  📎" : ""); color: root.ink; elide: Text.ElideRight; font.pixelSize: 11; font.weight: Font.DemiBold }
                                Text { width: parent.width; text: modelData.snippet || ""; color: root.muted; elide: Text.ElideRight; font.pixelSize: 9 }
                            }
                            TapHandler { onTapped: mailBridge.selectMessage(modelData.message_id) }
                        }
                    }
                    Text { visible: !root.permissionRequired && !mailBridge.loading && !!mailBridge.error; text: "⚠\nERREUR DE SYNCHRONISATION\nRÉESSAYER"; horizontalAlignment: Text.AlignHCenter; width: parent.width; wrapMode: Text.WordWrap; color: "#E6B86A"; font.pixelSize: 10 }
                    Text { visible: !root.permissionRequired && !mailBridge.loading && !mailBridge.error && mailBridge.messages.length === 0; text: "✉\nAUCUN MESSAGE À AFFICHER\nVotre boîte ne contient aucun message correspondant à ce filtre."; horizontalAlignment: Text.AlignHCenter; width: parent.width; wrapMode: Text.WordWrap; color: root.muted; font.pixelSize: 10 }
                }
            }
            Rectangle {
                objectName: "nativeMailPreviewPanel"; width: Math.max(180, parent.width - sidebar.width - center.width - 20); height: parent.height
                radius: 14; color: root.card; border.width: 1; border.color: "#3475A9B8"
                Column { anchors.fill: parent; anchors.margins: 14; spacing: 12
                    Text { objectName: "nativeMailPreviewTitle"; text: "APERÇU INTELLIGENT"; color: root.muted; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                    Text { visible: !mailBridge.selectedMessage.subject; width: parent.width; height: 100; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: "✉\nSÉLECTIONNEZ UN MESSAGE\nLe contenu, le résumé local et les actions apparaîtront ici."; color: root.muted; font.pixelSize: 10 }
                    Text { width: parent.width; wrapMode: Text.WordWrap; text: mailBridge.selectedMessage.subject || "Sélectionnez un message"; color: root.ink; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { width: parent.width; elide: Text.ElideRight; text: mailBridge.selectedMessage.sender || "L’aperçu apparaîtra ici."; color: root.muted; font.pixelSize: 10 }
                    Rectangle { objectName: "nativeMailSummaryCard"; visible: !!mailBridge.selectedSummary; width: parent.width; height: 68; radius: 12; color: root.lightMode ? "#E4EDF5" : "#17253D"; border.width: 1; border.color: "#6C5FC2A0"; Column { anchors.fill: parent; anchors.margins: 9; spacing: 4; Text { text: "AURA · " + mailBridge.selectedSummaryLabel; color: root.violet; font.pixelSize: 8; font.weight: Font.DemiBold } Text { width: parent.width; wrapMode: Text.WordWrap; text: mailBridge.selectedSummary; color: root.ink; font.pixelSize: 9 } } }
                    ScrollView { objectName: "nativeMailBodyScroll"; width: parent.width; height: Math.max(90, parent.height - 205); clip: true; contentWidth: availableWidth; contentHeight: bodyText.implicitHeight; ScrollBar.horizontal.policy: ScrollBar.AlwaysOff; ScrollBar.vertical.policy: ScrollBar.AsNeeded
                        ScrollBar.vertical.contentItem: Rectangle { implicitWidth: 5; radius: 3; color: root.violet; opacity: .72 }
                        Text { id: bodyText; width: parent.width; wrapMode: Text.WrapAnywhere; text: mailBridge.selectedMessage.body || mailBridge.selectedMessage.snippet || ""; color: root.ink; font.pixelSize: 12; lineHeight: 1.25; lineHeightMode: Text.ProportionalHeight }
                    }
                    Text { text: mailBridge.selectedMessage.attachments && mailBridge.selectedMessage.attachments.length ? "📎 Pièces jointes : " + mailBridge.selectedMessage.attachments.length : ""; color: root.muted; font.pixelSize: 9 }
                    AuraButton { visible: !!mailBridge.selectedMessage.thread_id; width: 154; lightMode: root.lightMode; text: "OUVRIR DANS GMAIL"; onClicked: mailBridge.openInGmail(mailBridge.selectedMessage.thread_id) }
                }
            }
        }
    }
}
