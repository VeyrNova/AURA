import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "../components"

Item {
    id: root

    // AURA_MODULES_LIQUID_GLASS_PREMIUM_FIX32
    property bool lightMode: false
    property Item backdropSource: null
    property string page: "modules"
    property real lensX: 0.28
    property real lensY: 0.22

    signal navigateRequested(string key)
    signal prefillRequested(string text)
    signal closeRequested()

    width: 372
    height: page === "mail" ? 404 : 490

    function choose(key) {
        if (key === "mail") {
            if (runtimeMode === "native") {
                navigateRequested("mail")
                return
            }
            page = "mail"
            return
        }
        if (key === "maps" || key === "weather") { navigateRequested(key); return }
        if (key === "research") { navigateRequested("search"); return }
        if (key === "documents") { navigateRequested("documents"); return }
        if (key === "notifications") { prefillRequested("affiche mes notifications"); return }
        if (key === "contacts") { navigateRequested("contacts"); return }
    }

    function iconSource(key) {
        return auraAssetBase + "module-" + key + "-premium.svg"
    }

    LiquidGlass {
        id: liquidBody
        anchors.fill: parent
        backdropSource: root.backdropSource
        sourceX: root.x
        sourceY: root.y
        lightMode: root.lightMode
        accent: root.page === "mail" ? "#74EFFF" : "#9D72FF"
        cornerRadius: 20
        blurStrength: 0.90
        saturationBoost: 0.32
        lensX: root.lensX
        lensY: root.lensY
        darkOpacity: 0.90
        lightOpacity: 0.90
    }

    // Cyan/violet edge bloom.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: 21
        color: "transparent"
        border.width: 1
        border.color: root.lightMode ? "#5488A8BA" : "#754BDFF5"
        opacity: 0.72
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 5
        radius: 16
        color: "transparent"
        border.width: 1
        border.color: root.lightMode ? "#35FFFFFF" : "#1DFFFFFF"
        opacity: 0.62
    }

    // Subtle violet inner glow at the lower-right.
    Rectangle {
        width: parent.width * .56
        height: parent.height * .28
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        radius: width / 2
        color: root.lightMode ? "#083C6A90" : "#154F20A7"
        opacity: 0.30
    }

    HoverHandler {
        id: panelHover
        onPointChanged: {
            root.lensX = Math.max(0, Math.min(1, point.position.x / Math.max(1, root.width)))
            root.lensY = Math.max(0, Math.min(1, point.position.y / Math.max(1, root.height)))
        }
    }

    Column {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Row {
            width: parent.width
            spacing: 8

            Column {
                width: parent.width - 102
                spacing: 2

                Text {
                    text: root.page === "mail" ? "MAIL" : "MODULES"
                    color: root.lightMode ? "#163D54" : "#F0FCFF"
                    font.family: "Segoe UI Variable"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    font.letterSpacing: 2.8
                }

                Text {
                    text: root.page === "mail"
                          ? "Raccourcis mail · backend AURA"
                          : "Sous-dock liquid glass"
                    color: root.lightMode ? "#607D8D" : "#7595A7"
                    font.pixelSize: 8
                }
            }

            Rectangle {
                width: 62
                height: 29
                radius: 9
                color: root.lightMode ? "#D7FFFFFF" : "#6C081520"
                border.width: 1
                border.color: root.page === "mail" ? "#5074EFFF" : "#5E8F70F5"

                Text {
                    anchors.centerIn: parent
                    text: root.page === "mail" ? "MAIL" : "7 MOD"
                    color: root.lightMode ? "#3A6275" : "#B5F2FA"
                    font.pixelSize: 7
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.0
                }
            }

            Rectangle {
                width: 29
                height: 29
                radius: 9
                color: closeHover.hovered
                       ? (root.lightMode ? "#F5FFFFFF" : "#4C17304B")
                       : (root.lightMode ? "#D8FFFFFF" : "#4B08121A")
                border.width: 1
                border.color: closeHover.hovered ? "#9D72FF" : (root.lightMode ? "#456E8C9F" : "#3A72DDEB")

                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: root.lightMode ? "#476C7B" : "#C7F5FB"
                    font.pixelSize: 16
                }

                HoverHandler { id: closeHover }
                TapHandler { onTapped: root.closeRequested() }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#0074EFFF" }
                GradientStop { position: 0.50; color: root.lightMode ? "#4D4EA4BB" : "#5074EFFF" }
                GradientStop { position: 1.0; color: "#009D72FF" }
            }
        }

        Flickable {
            visible: root.page === "modules"
            width: parent.width
            height: parent.height - y
            contentWidth: width
            contentHeight: moduleColumn.height
            clip: true

            Column {
                id: moduleColumn
                width: parent.width
                spacing: 8

                Repeater {
                    model: ListModel {
                        ListElement { key: "maps"; title: "MAPS"; sub: "Trajets · POI · Travel Brief"; accent: "#74EFFF" }
                        ListElement { key: "weather"; title: "MÉTÉO"; sub: "Prévisions · carte météo"; accent: "#5AD8FF" }
                        ListElement { key: "search"; title: "RECHERCHE"; sub: "Recherche IA avec sources"; accent: "#A47CFF" }
                        ListElement { key: "documents"; title: "DOCUMENTS"; sub: "Gérer, rechercher ou joindre un fichier"; accent: "#8DE3FF" }
                        ListElement { key: "notifications"; title: "NOTIFICATIONS"; sub: "Centre d’activité et alertes"; accent: "#D887FF" }
                        ListElement { key: "mail"; title: "MAIL"; sub: "Courriels · recherche · brouillons · envoi"; accent: "#74EFFF" }
                        ListElement { key: "contacts"; title: "CONTACTS"; sub: "Recherche & gestion"; accent: "#8B9CFF" }
                    }

                    Rectangle {
                        required property string key
                        required property string title
                        required property string sub
                        required property string accent

                        width: moduleColumn.width
                        height: 54
                        radius: 13

                        color: rowHover.hovered
                               ? (root.lightMode ? "#DFFFFFFF" : "#710E2031")
                               : (root.lightMode ? "#B8FFFFFF" : "#4F06121E")
                        border.width: 1
                        border.color: rowHover.hovered
                                      ? accent
                                      : (root.lightMode ? "#3C62849B" : "#305E7B98")

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1
                            radius: 12
                            color: "transparent"
                            border.width: 1
                            border.color: root.lightMode ? "#45FFFFFF" : "#0EFFFFFF"
                        }

                        // Premium icon glass capsule.
                        Rectangle {
                            id: iconCapsule
                            x: 9
                            y: 7
                            width: 40
                            height: 40
                            radius: 12
                            color: root.lightMode ? "#DDF8FCFF" : "#80101B2A"
                            border.width: 1
                            border.color: accent

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 2
                                radius: 10
                                color: rowHover.hovered ? "#182F3E66" : "transparent"
                            }

                            Image {
                                id: moduleIcon
                                anchors.centerIn: parent
                                width: 25
                                height: 25
                                source: root.iconSource(key)
                                fillMode: Image.PreserveAspectFit
                                mipmap: true
                            }

                            MultiEffect {
                                anchors.fill: moduleIcon
                                source: moduleIcon
                                shadowEnabled: true
                                shadowColor: accent
                                shadowBlur: 1.0
                                shadowOpacity: rowHover.hovered ? 0.95 : 0.62
                            }
                        }

                        Column {
                            x: 61
                            y: 10
                            width: parent.width - 92
                            spacing: 3

                            Text {
                                text: title
                                color: root.lightMode ? "#163F56" : "#ECFBFF"
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.25
                            }

                            Text {
                                width: parent.width
                                text: sub
                                elide: Text.ElideRight
                                color: root.lightMode ? "#607C8D" : "#7593A5"
                                font.pixelSize: 7
                            }
                        }

                        HoverHandler { id: rowHover }

                        TapHandler {
                            onTapped: {
                                var logicalKey = key === "search" ? "research" : key
                                root.choose(logicalKey)
                            }
                        }
                    }
                }

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: "SYSTEM LIVE reste dans Diagnostics."
                    color: root.lightMode ? "#728996" : "#526F80"
                    font.pixelSize: 7
                }
            }
        }

        Column {
            visible: root.page === "mail"
            width: parent.width
            spacing: 9

            Rectangle {
                width: parent.width
                height: 40
                radius: 11
                color: root.lightMode ? "#CFFFFFFF" : "#5B07131E"
                border.width: 1
                border.color: root.lightMode ? "#3E607F97" : "#3476E5F4"

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "MAIL RAPIDE"
                    color: root.lightMode ? "#20485E" : "#DDFBFF"
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: 66
                    height: 25
                    radius: 8
                    color: "transparent"
                    border.width: 1
                    border.color: "#3A76E5F4"

                    Text {
                        anchors.centerIn: parent
                        text: "RETOUR"
                        color: root.lightMode ? "#436B7D" : "#8BEAF8"
                        font.pixelSize: 7
                    }

                    TapHandler { onTapped: root.page = "modules" }
                }
            }

            Repeater {
                model: ListModel {
                    ListElement { key: "inbox"; title: "BOÎTE DE RÉCEPTION"; sub: "Afficher les mails" }
                    ListElement { key: "search"; title: "RECHERCHER"; sub: "Rechercher dans les mails" }
                    ListElement { key: "draft"; title: "BROUILLON"; sub: "Préparer un message" }
                    ListElement { key: "send"; title: "ENVOYER"; sub: "Confirmation AURA requise" }
                }

                Rectangle {
                    required property string key
                    required property string title
                    required property string sub

                    width: parent.width
                    height: 56
                    radius: 13
                    color: mailHover.hovered
                           ? (root.lightMode ? "#DFFFFFFF" : "#710E2031")
                           : (root.lightMode ? "#B8FFFFFF" : "#4F06121E")
                    border.width: 1
                    border.color: mailHover.hovered ? "#74EFFF" : (root.lightMode ? "#3C62849B" : "#305E7B98")

                    Rectangle {
                        x: 9; y: 8; width: 40; height: 40; radius: 12
                        color: root.lightMode ? "#DDF8FCFF" : "#80101B2A"
                        border.width: 1
                        border.color: "#74EFFF"

                        Image {
                            anchors.centerIn: parent
                            width: 24; height: 24
                            source: auraAssetBase + "module-mail-premium.svg"
                            fillMode: Image.PreserveAspectFit
                            mipmap: true
                        }
                    }

                    Column {
                        x: 61; y: 11; width: parent.width - 78; spacing: 3
                        Text { text: title; color: root.lightMode ? "#163F56" : "#ECFBFF"; font.pixelSize: 9; font.weight: Font.DemiBold }
                        Text { text: sub; color: root.lightMode ? "#607C8D" : "#7593A5"; font.pixelSize: 7 }
                    }

                    HoverHandler { id: mailHover }

                    TapHandler {
                        onTapped: {
                            if (runtimeMode === "native" && mailBridge) mailBridge.setMode(key)
                            root.navigateRequested("mail")
                        }
                    }
                }
            }
        }
    }
}
