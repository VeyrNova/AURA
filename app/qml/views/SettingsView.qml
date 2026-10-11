import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    // AURA_SETTINGS_LANGUAGE_FIX10
    property bool lightMode: false

    AuraWorkspacePanel { anchors.fill: parent; z: -1; lightMode: root.lightMode }

    ProviderIntegrationsView { anchors.fill: parent; z: 10; lightMode: root.lightMode; visible: root.visible }

    GlassPanel {
        id: panel
        visible: false
        x: 12
        y: 12
        width: Math.min(420, root.width - 24)
        height: 332
        radius: 20
        lightMode: root.lightMode
        accent: "#74EFFF"

        Rectangle { anchors.fill: parent; anchors.margins: 1; radius: 19; color: root.lightMode ? "#F8FBFCF2" : "#F0050D1C"; border.width: 0 }

        Rectangle {
            id: header
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            height: 48; radius: 20; color: root.lightMode ? "#E8F7FAFC" : "#ED071323"
            Rectangle { anchors.left:parent.left; anchors.right:parent.right; anchors.bottom:parent.bottom; height:1; color:root.lightMode?"#245D8798":"#1769D5E7" }
            Column {
                anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; anchors.leftMargin: 14; spacing: 3
                Text { text:"AURA WORKSPACE"; color:root.lightMode?"#667D8B":"#596582"; font.pixelSize:7; font.letterSpacing:1.5 }
                Text { text:"PARAMÈTRES"; color:root.lightMode?"#294E62":"#C9CCE9"; font.pixelSize:11; font.weight:Font.DemiBold; font.letterSpacing:.9 }
            }
            Rectangle {
                anchors.right:parent.right; anchors.verticalCenter:parent.verticalCenter; anchors.rightMargin:12
                width:28; height:28; radius:8; color:root.lightMode?"#AFFFFFFF":"#61231D42"; border.width:1; border.color:root.lightMode?"#285C8295":"#31717AB1"
                Text { anchors.centerIn:parent; text:"×"; color:root.lightMode?"#607583":"#8B93B2"; font.pixelSize:12 }
                TapHandler { onTapped: bridge.setWorkspace("home") }
            }
        }

        Column {
            anchors.left:parent.left; anchors.right:parent.right; anchors.top:header.bottom; anchors.bottom:parent.bottom; anchors.margins:14; spacing:0
            Text { text:"Configuration locale AURA"; color:root.lightMode?"#314F61":"#C9CCE9"; font.pixelSize:11; font.weight:Font.DemiBold }
            Text { width:parent.width; topPadding:7; bottomPadding:11; wrapMode:Text.WordWrap; text:"Les réglages techniques existants restent inchangés afin de ne pas modifier le runtime validé."; color:root.lightMode?"#6F818D":"#69738F"; font.pixelSize:8; lineHeight:1.45 }
            SettingRow { lightMode:root.lightMode; labelText:"Profil"; valueText:"Standard" }
            SettingRow { lightMode:root.lightMode; labelText:"Runtime"; valueText:"Local + hybride" }
            SettingRow { lightMode:root.lightMode; labelText:"Workspace"; valueText:"Qt Quick · Headless Core" }
            Rectangle {
                width:parent.width; height:110; radius:14; color:root.lightMode?"#AFFFFFFF":"#7A061222"; border.width:1; border.color:root.lightMode?"#2D5D8799":"#2E78DCFF"
                Column {
                    anchors.fill:parent; anchors.margins:12; spacing:8
                    Text { text:"GÉNÉRAL / GENERAL"; color:root.lightMode?"#647C89":"#72899B"; font.pixelSize:7; font.letterSpacing:.9 }
                    Text { text:"LANGUE / LANGUAGE"; color:root.lightMode?"#345F70":"#9CCEDB"; font.pixelSize:8; font.weight:Font.DemiBold; font.letterSpacing:.65 }
                    Row {
                        width:parent.width; spacing:8
                        Repeater {
                            model:[["FRANÇAIS","fr-FR"],["ENGLISH","en-US"]]
                            delegate: Rectangle {
                                width:(parent.width-8)/2; height:31; radius:10
                                property bool selected: coreBridge.locale===modelData[1]
                                color:selected?(root.lightMode?"#CDEFF8FA":"#471D6174"):(root.lightMode?"#AFFFFFFF":"#600B1B2F")
                                border.width:1; border.color:selected?"#4A74DCEC":(root.lightMode?"#2C5D8799":"#4278DFFC")
                                Text { anchors.centerIn:parent; text:modelData[0]; color:selected?(root.lightMode?"#22586E":"#B9EFFF"):(root.lightMode?"#697E8A":"#819BAA"); font.pixelSize:7; font.weight:selected?Font.DemiBold:Font.Normal }
                                TapHandler { onTapped: coreBridge.setLocale(modelData[1]) }
                            }
                        }
                    }
                    Text { width:parent.width; elide:Text.ElideRight; text:coreBridge.locale==="en-US"?"Text, speech recognition and Camilla follow this language.":"Le texte, la reconnaissance vocale et Camilla suivent cette langue."; color:root.lightMode?"#72848F":"#6C8392"; font.pixelSize:7 }
                }
            }
        }
    }

    component SettingRow: Rectangle {
        property bool lightMode:false
        property string labelText:""
        property string valueText:""
        width:parent?parent.width:300; height:34; color:"transparent"
        Rectangle { anchors.left:parent.left; anchors.right:parent.right; anchors.top:parent.top; height:1; color:lightMode?"#185B8494":"#1A636F9D" }
        Row {
            anchors.fill:parent; anchors.topMargin:1
            Text { width:parent.width/2; anchors.verticalCenter:parent.verticalCenter; text:labelText; color:lightMode?"#667D89":"#65708E"; font.pixelSize:8 }
            Text { width:parent.width/2; anchors.verticalCenter:parent.verticalCenter; horizontalAlignment:Text.AlignRight; text:valueText; color:lightMode?"#405C6D":"#A2A8C8"; font.pixelSize:8; font.weight:Font.Medium }
        }
    }
}
