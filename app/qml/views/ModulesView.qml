import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root

    // AURA_MODULES_NATIVE_FIX30
    property bool lightMode: false
    property string activePanel: "catalog"

    signal navigateRequested(string key)
    signal conversationPrefillRequested(string text)

    function openConversationPrefill(text) {
        root.conversationPrefillRequested(String(text || ""))
    }

    function openCatalogModule(key) {
        if (key === "mail") {
            root.navigateRequested("mail")
            return
        }
        if (key === "maps") {
            root.navigateRequested("maps")
            return
        }
        if (key === "weather") {
            root.navigateRequested("weather")
            return
        }
        if (key === "research") {
            root.navigateRequested("search")
            return
        }
        if (key === "documents") {
            root.navigateRequested("documents")
            return
        }
        if (key === "notifications") {
            root.openConversationPrefill("affiche mes notifications")
            return
        }
        if (key === "contacts") {
            root.navigateRequested("contacts")
            return
        }
    }

    ContextDrawer {
        id: drawer
        lightMode: root.lightMode
        drawerWidth: 900
        titleText: root.activePanel === "mail" ? "MAIL" : "MODULES"
        subtitleText: root.activePanel === "mail"
                      ? "AURA PERSONAL INTEGRATIONS · backend AURA"
                      : "AURA WORKSPACE · intégrations et outils"
        accentColor: root.activePanel === "mail" ? "#74EFFF" : "#9A78FF"

        Rectangle {
            parent: drawer.headerActions
            width: root.activePanel === "mail" ? 82 : 98
            height: 30
            radius: 9
            color: root.lightMode ? "#E8FFFFFF" : "#82081724"
            border.width: 1
            border.color: root.activePanel === "mail" ? "#3574E6F5" : "#407B6BDA"

            Text {
                anchors.centerIn: parent
                text: root.activePanel === "mail" ? "MAIL" : "7 MODULES"
                color: root.lightMode ? "#375B72" : "#A9EAF5"
                font.pixelSize: 7
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
            }
        }

        Item {
            parent: drawer.contentItem
            anchors.fill: parent

            Flickable {
                id: catalogScroll
                visible: root.activePanel === "catalog"
                anchors.fill: parent
                anchors.margins: 18
                clip: true
                contentWidth: width
                contentHeight: catalogColumn.height

                Column {
                    id: catalogColumn
                    width: catalogScroll.width
                    spacing: 14

                    Rectangle {
                        width: parent.width
                        height: 72
                        radius: 14
                        color: root.lightMode ? "#B7FFFFFF" : "#66060E19"
                        border.width: 1
                        border.color: root.lightMode ? "#345E8CA4" : "#2879DFF0"

                        Row {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 14

                            Rectangle {
                                width: 42
                                height: 42
                                radius: 13
                                anchors.verticalCenter: parent.verticalCenter
                                color: root.lightMode ? "#DFF7FBFD" : "#760B1425"
                                border.width: 1
                                border.color: "#4F8E69E5"

                                Text {
                                    anchors.centerIn: parent
                                    text: "◇"
                                    color: root.lightMode ? "#6A4BC2" : "#B38DFF"
                                    font.pixelSize: 20
                                }
                            }

                            Column {
                                width: parent.width - 56
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4

                                Text {
                                    text: "AURA MODULE FABRIC"
                                    color: root.lightMode ? "#244B62" : "#D4F7FF"
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.5
                                }

                                Text {
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    text: "Accès natif Qt aux modules personnels et workspaces historiques de la version Chromium."
                                    color: root.lightMode ? "#657F8E" : "#718FA1"
                                    font.pixelSize: 8
                                }
                            }
                        }
                    }

                    Grid {
                        id: moduleGrid
                        width: parent.width
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 12

                        Repeater {
                            model: ListModel {
                                ListElement { key: "maps"; title: "MAPS"; subtitle: "Trajets · POI · Travel Brief"; glyph: "⌖"; accent: "#74EFFF" }
                                ListElement { key: "weather"; title: "MÉTÉO"; subtitle: "Prévisions · carte météo"; glyph: "☁"; accent: "#62D9FF" }
                                ListElement { key: "research"; title: "RECHERCHE"; subtitle: "Recherche IA avec sources"; glyph: "⌕"; accent: "#A47CFF" }
                                ListElement { key: "documents"; title: "DOCUMENTS"; subtitle: "Gérer, rechercher ou joindre un fichier"; glyph: "▱"; accent: "#8DE3FF" }
                                ListElement { key: "notifications"; title: "NOTIFICATIONS"; subtitle: "Centre d’activité et alertes"; glyph: "◎"; accent: "#D887FF" }
                                ListElement { key: "mail"; title: "MAIL"; subtitle: "Courriels · recherche · brouillons · envoi"; glyph: "✉"; accent: "#74EFFF" }
                                ListElement { key: "contacts"; title: "CONTACTS"; subtitle: "Recherche & gestion"; glyph: "◉"; accent: "#8B9CFF" }
                            }

                            Rectangle {
                                required property string key
                                required property string title
                                required property string subtitle
                                required property string glyph
                                required property string accent

                                width: (moduleGrid.width - moduleGrid.columnSpacing) / 2
                                height: 108
                                radius: 14
                                color: cardHover.hovered
                                       ? (root.lightMode ? "#F5FFFFFF" : "#920A1523")
                                       : (root.lightMode ? "#C8F9FCFD" : "#72050D18")
                                border.width: 1
                                border.color: cardHover.hovered
                                              ? accent
                                              : (root.lightMode ? "#2C5A8298" : "#285F78A0")

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 2
                                    anchors.topMargin: 13
                                    anchors.bottomMargin: 13
                                    radius: 1
                                    color: accent
                                    opacity: cardHover.hovered ? .95 : .48
                                }

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 13

                                    Rectangle {
                                        width: 46
                                        height: 46
                                        radius: 14
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: root.lightMode ? "#EAFFFFFF" : "#70071120"
                                        border.width: 1
                                        border.color: accent

                                        Text {
                                            anchors.centerIn: parent
                                            text: glyph
                                            color: accent
                                            font.pixelSize: 20
                                        }
                                    }

                                    Column {
                                        width: parent.width - 59
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 6

                                        Text {
                                            text: title
                                            color: root.lightMode ? "#183F55" : "#DDF8FF"
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                            font.letterSpacing: 1.3
                                        }

                                        Text {
                                            width: parent.width
                                            text: subtitle
                                            wrapMode: Text.WordWrap
                                            color: root.lightMode ? "#617D8D" : "#6E8EA1"
                                            font.pixelSize: 8
                                            lineHeight: 1.25
                                        }
                                    }
                                }

                                HoverHandler { id: cardHover }
                                TapHandler { onTapped: root.openCatalogModule(key) }
                            }
                        }
                    }

                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: "SYSTEM LIVE reste volontairement hors de Modules : Diagnostics conserve son workspace dédié."
                        color: root.lightMode ? "#738A97" : "#516F80"
                        font.pixelSize: 7
                        lineHeight: 1.4
                    }
                }
            }

            Flickable {
                id: mailScroll
                visible: root.activePanel === "mail"
                anchors.fill: parent
                anchors.margins: 18
                clip: true
                contentWidth: width
                contentHeight: mailColumn.height

                Column {
                    id: mailColumn
                    width: mailScroll.width
                    spacing: 14

                    Rectangle {
                        width: parent.width
                        height: 78
                        radius: 14
                        color: root.lightMode ? "#C8F9FCFD" : "#72050E18"
                        border.width: 1
                        border.color: root.lightMode ? "#335A8299" : "#3078DFF0"

                        Row {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 14

                            Rectangle {
                                width: 44
                                height: 44
                                radius: 13
                                anchors.verticalCenter: parent.verticalCenter
                                color: root.lightMode ? "#E8FFFFFF" : "#76081724"
                                border.width: 1
                                border.color: "#3C78E5F4"

                                Text {
                                    anchors.centerIn: parent
                                    text: "✉"
                                    color: root.lightMode ? "#24697E" : "#86EBF8"
                                    font.pixelSize: 20
                                }
                            }

                            Column {
                                width: parent.width - 154
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4

                                Text {
                                    text: "MAIL · MODE SYNTHÉTIQUE"
                                    color: root.lightMode ? "#244B62" : "#D3F7FF"
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                }

                                Text {
                                    text: "Le backend AURA reste l’autorité. Les actions sensibles conservent leur confirmation."
                                    color: root.lightMode ? "#657F8E" : "#6E8FA1"
                                    font.pixelSize: 8
                                }
                            }

                            Rectangle {
                                width: 78
                                height: 32
                                radius: 9
                                anchors.verticalCenter: parent.verticalCenter
                                color: backHover.hovered
                                       ? (root.lightMode ? "#F7FFFFFF" : "#1D74EFFF")
                                       : "transparent"
                                border.width: 1
                                border.color: root.lightMode ? "#325C8CA3" : "#2874DDED"

                                Text {
                                    anchors.centerIn: parent
                                    text: "RETOUR"
                                    color: root.lightMode ? "#436A7B" : "#84DEEC"
                                    font.pixelSize: 7
                                    font.letterSpacing: 0.9
                                }

                                HoverHandler { id: backHover }
                                TapHandler { onTapped: root.activePanel = "catalog" }
                            }
                        }
                    }

                    Grid {
                        id: mailGrid
                        width: parent.width
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 12

                        Repeater {
                            model: ListModel {
                                ListElement { actionKey: "inbox"; label: "BOÎTE DE RÉCEPTION"; detail: "Afficher les mails"; glyph: "▤" }
                                ListElement { actionKey: "search"; label: "RECHERCHER"; detail: "Rechercher dans les mails"; glyph: "⌕" }
                                ListElement { actionKey: "draft"; label: "BROUILLON"; detail: "Préparer un message"; glyph: "▱" }
                                ListElement { actionKey: "send"; label: "ENVOYER"; detail: "Confirmation AURA requise"; glyph: "➤" }
                            }

                            Rectangle {
                                required property string actionKey
                                required property string label
                                required property string detail
                                required property string glyph

                                width: (mailGrid.width - mailGrid.columnSpacing) / 2
                                height: 104
                                radius: 14
                                color: mailHover.hovered
                                       ? (root.lightMode ? "#F6FFFFFF" : "#92091624")
                                       : (root.lightMode ? "#C8F9FCFD" : "#70050D18")
                                border.width: 1
                                border.color: mailHover.hovered
                                              ? "#74EFFF"
                                              : (root.lightMode ? "#2D5C839B" : "#285F789A")

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 15
                                    spacing: 13

                                    Rectangle {
                                        width: 44
                                        height: 44
                                        radius: 13
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: root.lightMode ? "#EAFFFFFF" : "#70081724"
                                        border.width: 1
                                        border.color: "#3977DFF0"

                                        Text {
                                            anchors.centerIn: parent
                                            text: glyph
                                            color: root.lightMode ? "#276A81" : "#83E7F6"
                                            font.pixelSize: 18
                                        }
                                    }

                                    Column {
                                        width: parent.width - 57
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 6

                                        Text {
                                            text: label
                                            color: root.lightMode ? "#183F55" : "#DDF8FF"
                                            font.pixelSize: 9
                                            font.weight: Font.DemiBold
                                            font.letterSpacing: 1.0
                                        }

                                        Text {
                                            width: parent.width
                                            text: detail
                                            wrapMode: Text.WordWrap
                                            color: root.lightMode ? "#617D8D" : "#6E8EA1"
                                            font.pixelSize: 8
                                        }
                                    }
                                }

                                HoverHandler { id: mailHover }

                                TapHandler {
                                    onTapped: {
                                        if (actionKey === "inbox") {
                                            if (coreBridge.sendMessage("affiche mes mails"))
                                                root.navigateRequested("talk")
                                        } else if (actionKey === "search") {
                                            root.openConversationPrefill("cherche mes mails sur ")
                                        } else if (actionKey === "draft") {
                                            root.openConversationPrefill("prepare un brouillon de mail a ")
                                        } else if (actionKey === "send") {
                                            root.openConversationPrefill("envoie un mail a ")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
