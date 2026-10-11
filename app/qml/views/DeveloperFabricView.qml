import QtQuick
import QtQuick.Controls

Item {
    id: root
    property bool lightMode: false
    readonly property color bg: lightMode ? "#EAF4F7" : "#07131E"
    readonly property color card: lightMode ? "#F4FAFC" : "#0A202D"
    readonly property color text0: lightMode ? "#17394D" : "#D8F7FF"
    readonly property color text1: lightMode ? "#557487" : "#84A8B7"
    readonly property color accent: "#F0A23A"
    Rectangle { anchors.fill: parent; radius: 16; color: root.bg; border.color: root.accent; border.width: 1 }
    Flickable {
        anchors.fill: parent; anchors.margins: 22; contentWidth: width; contentHeight: body.implicitHeight
        clip: true
        Column { id: body; width: parent.width; spacing: 14
            Row { width: parent.width; spacing: 14
                Column { width: parent.width - 210; spacing: 4
                    Text { text: "AURA DEVELOPER FABRIC"; color: root.text0; font.pixelSize: 22; font.weight: Font.DemiBold }
                    Text { text: developerFabricBridge.developerModeEnabled ? "MODE DÉVELOPPEUR ACTIVÉ" : "MODE DÉVELOPPEUR DÉSACTIVÉ"; color: developerFabricBridge.developerModeEnabled ? root.accent : root.text1; font.pixelSize: 12 }
                }
                Rectangle { width: 190; height: 38; radius: 10; color: root.card; border.color: root.accent
                    Text { anchors.centerIn: parent; text: developerFabricBridge.developerModeEnabled ? "DÉSACTIVER" : "ACTIVER"; color: root.text0 }
                    MouseArea { anchors.fill: parent; onClicked: developerFabricBridge.developerModeEnabled ? developerFabricBridge.disableDeveloperMode() : developerFabricBridge.enableDeveloperMode() }
                }
            }
            Rectangle { width: parent.width; height: 76; radius: 12; color: root.card
                Column { anchors.fill: parent; anchors.margins: 12; spacing: 4
                    Text { text: "PROJET ACTIF"; color: root.accent; font.pixelSize: 11 }
                    Text { text: developerFabricBridge.hasActiveProject ? developerFabricBridge.activeProjectName + " · " + developerFabricBridge.activeWorkspace : "Aucun projet sélectionné"; color: root.text0; elide: Text.ElideRight; width: parent.width }
                }
            }
            Rectangle { width: parent.width; height: 112; radius: 12; color: root.card
                Column { anchors.fill: parent; anchors.margins: 12; spacing: 8
                    Text { text: "NOUVELLE DEMANDE"; color: root.accent; font.pixelSize: 11 }
                    Row { width: parent.width; spacing: 8
                        TextField { id: request; width: parent.width - 150; placeholderText: "Que veux-tu modifier ou développer ?"; enabled: developerFabricBridge.developerModeEnabled && developerFabricBridge.hasActiveProject }
                        Rectangle { width: 140; height: 38; radius: 9; color: request.enabled && request.text.length ? root.accent : "#52616A"; opacity: request.enabled && request.text.length ? 1 : .55
                            Text { anchors.centerIn: parent; text: "CRÉER LE PLAN"; color: "#07131E" }
                            MouseArea { anchors.fill: parent; enabled: request.enabled && request.text.length > 0; onClicked: developerFabricBridge.createDeveloperJob(request.text) }
                        }
                    }
                }
            }
            Row { width: parent.width; spacing: 14
                Rectangle { width: parent.width * .48; height: 260; radius: 12; color: root.card
                    Column { anchors.fill: parent; anchors.margins: 12; spacing: 8
                        Text { text: "JOBS"; color: root.accent; font.pixelSize: 11 }
                        Text { text: developerFabricBridge.currentJobId.length ? developerFabricBridge.currentJobState : "Aucun job sélectionné"; color: root.text0 }
                        Text { text: developerFabricBridge.currentJobHasDiff ? "Diff disponible" : "Diff non disponible"; color: root.text1 }
                        Text { text: "WORKFLOW · REQUEST → PLAN → TEST → APPROVAL → APPLY → DONE"; color: root.text1; wrapMode: Text.Wrap; width: parent.width }
                        Text { text: "Agents disponibles : " + developerAgentsModel.count; color: root.text1 }
                        Row { spacing: 8
                            Rectangle { width: 92; height: 30; radius: 7; color: root.accent; visible: developerFabricBridge.currentJobId.length > 0 && developerFabricBridge.currentJobState === "CREATED"; Text { anchors.centerIn: parent; text: "PLAN"; color: "#07131E" }
 MouseArea { anchors.fill: parent; onClicked: developerFabricBridge.planDeveloperJob(developerFabricBridge.currentJobId) } }
                            Rectangle { width: 92; height: 30; radius: 7; color: root.accent; visible: developerFabricBridge.currentJobState === "PLANNED"; Text { anchors.centerIn: parent; text: "STAGE"; color: "#07131E" }
 MouseArea { anchors.fill: parent; onClicked: developerFabricBridge.stageDeveloperJob(developerFabricBridge.currentJobId) } }
                            Rectangle { width: 150; height: 30; radius: 7; color: root.accent; visible: developerFabricBridge.currentJobCanApprove; Text { anchors.centerIn: parent; text: "APPROUVER / APPLIQUER"; color: "#07131E"; font.pixelSize: 10 }
 MouseArea { anchors.fill: parent; onClicked: developerFabricBridge.approveAndApplyDeveloperJob(developerFabricBridge.currentJobId) } }
                        }
                    }
                }
                Rectangle { width: parent.width * .52 - 14; height: 260; radius: 12; color: root.card
                    Column { anchors.fill: parent; anchors.margins: 12; spacing: 8
                        Text { text: "AGENTS / PROVIDERS"; color: root.accent; font.pixelSize: 11 }
                        ListView { width: parent.width; height: 205; model: developerAgentsModel; clip: true; delegate: Text { required property string displayName; text: displayName; color: root.text0; height: 20 } }
                    }
                }
            }
            Text { text: "Approval, tests, diff et rollback restent verrouillés tant que le job réel ne remplit pas les prérequis."; color: root.text1; wrapMode: Text.Wrap; width: parent.width }
        }
    }
}



