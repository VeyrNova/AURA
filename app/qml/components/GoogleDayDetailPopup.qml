import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: popup
    objectName: "googleDayDetailPopup"
    property string day: ""
    property var summary: ({})
    property int initialTab: 0
    width: Math.min(620, parent ? parent.width - 32 : 620)
    height: Math.min(420, parent ? parent.height - 32 : 420)
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { radius: 18; color: "#F20A1A28"; border.width: 1; border.color: "#5574EFFF" }
    contentItem: Column {
        anchors.fill: parent; anchors.margins: 18; spacing: 12
        Row {
            width: parent.width; height: 30; spacing: 10
            GoogleCalendarIcon { width: 22; height: 22; anchors.verticalCenter: parent.verticalCenter }
            Column { width: parent.width - 72; spacing: 1
                Text { text: "JOURNÉE GOOGLE"; color: "#7899A8"; font.pixelSize: 8; font.letterSpacing: 1.2 }
                Text { text: popup.day; color: "#D8F9FF"; font.pixelSize: 14; font.weight: Font.DemiBold }
            }
            Rectangle { objectName: "googleDayPopupClose"; width: 30; height: 30; radius: 9; color: closeHover.hovered ? "#2A3C6173" : "#160D1B29"; border.width: 1; border.color: "#3A5D8EA0"
                Text { anchors.centerIn: parent; text: "×"; color: "#B8EFFF"; font.pixelSize: 18 }
                HoverHandler { id: closeHover }
                TapHandler { onTapped: popup.close() }
            }
        }
        Row {
            id: tabs; objectName: "googleDayPopupTabs"; property int currentIndex: popup.initialTab
            width: parent.width; height: 36; spacing: 5
            Rectangle { objectName: "googleDayCalendarTab"; width: (tabs.width - 10) / 3; height: 36; radius: 10; color: tabs.currentIndex === 0 ? "#2A4E687D" : "#17283A"; border.width: 1; border.color: tabs.currentIndex === 0 ? "#438DD8EA" : "#2A5C7380"
                Row { anchors.centerIn: parent; spacing: 4
                    GoogleCalendarIcon { width: 13; height: 13; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "CALENDRIER  " + Number(popup.summary.calendarCount || 0); color: tabs.currentIndex === 0 ? "#D8F9FF" : "#7695A4"; font.pixelSize: 8; anchors.verticalCenter: parent.verticalCenter }
                }
                TapHandler { onTapped: tabs.currentIndex = 0 }
            }
            Rectangle { objectName: "googleDayMailTab"; width: (tabs.width - 10) / 3; height: 36; radius: 10; color: tabs.currentIndex === 1 ? "#2A4E687D" : "#17283A"; border.width: 1; border.color: tabs.currentIndex === 1 ? "#438DD8EA" : "#2A5C7380"
                Row { anchors.centerIn: parent; spacing: 4
                    GoogleFavicon { iconSize: 13; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "MAILS  " + Number(popup.summary.mailCount || 0); color: tabs.currentIndex === 1 ? "#D8F9FF" : "#7695A4"; font.pixelSize: 8; anchors.verticalCenter: parent.verticalCenter }
                }
                TapHandler { onTapped: tabs.currentIndex = 1 }
            }
            Rectangle { objectName: "googleDayTasksTab"; width: (tabs.width - 10) / 3; height: 36; radius: 10; color: tabs.currentIndex === 2 ? "#2A4E687D" : "#17283A"; border.width: 1; border.color: tabs.currentIndex === 2 ? "#438DD8EA" : "#2A5C7380"
                Text { anchors.centerIn: parent; text: "✓  TÂCHES  " + Number(popup.summary.taskCount || 0); color: tabs.currentIndex === 2 ? "#D8F9FF" : "#7695A4"; font.pixelSize: 8 }
                TapHandler { onTapped: tabs.currentIndex = 2 }
            }
        }
        StackLayout { currentIndex: tabs.currentIndex; width: parent.width; height: Math.max(120, parent.height - 130)
            ListView { objectName: "googleDayCalendarList"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: popup.summary.calendarEvents || []; delegate: Text { width: parent.width; height: 28; color: "#B9DDE8"; text: (modelData.start || "Toute la journée").slice(11,16) + "  " + (modelData.title || "Sans titre"); elide: Text.ElideRight }
                Text { objectName: "googleDayCalendarEmpty"; anchors.centerIn: parent; visible: parent.count === 0; text: "Aucun événement pour cette date"; color: "#7896A3" }
            }
            Item { Layout.fillWidth: true; Layout.fillHeight: true
                Text { id: mailPermission; anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter; visible: popup.summary.mailState === "permission_required"; text: "! Autorisation Gmail requise"; color: "#FFD580" }
                ListView { objectName: "googleDayMailList"; anchors.fill: parent; anchors.topMargin: mailPermission.visible ? 24 : 0; clip: true; model: popup.summary.mails || []; delegate: Rectangle { width: parent.width; height: 58; color: "transparent"
                    Text { anchors.left: parent.left; anchors.right: parent.right; text: (modelData.sender || "Expéditeur") + " · " + (modelData.subject || "Sans objet"); color: "#D8F9FF"; elide: Text.ElideRight }
                    Text { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: 23; text: modelData.snippet || "Résumé en cours…"; color: "#9ABAC5"; elide: Text.ElideRight }
                    Text { anchors.right: parent.right; anchors.bottom: parent.bottom; text: modelData.attachments && modelData.attachments.length ? "📎" : ""; color: "#AEEFFF" }
                } }
                Text { objectName: "googleDayMailEmpty"; anchors.centerIn: parent; visible: (popup.summary.mails || []).length === 0 && popup.summary.mailState !== "permission_required"; text: "Aucun mail pour cette date"; color: "#7896A3" }
            }
            ListView { objectName: "googleDayTasksList"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: popup.summary.tasks || []; delegate: Text { width: parent.width; height: 28; color: modelData.status === "completed" ? "#66818E" : "#B9DDE8"; text: (modelData.status === "completed" ? "☑ " : "☐ ") + (modelData.title || "Sans titre"); elide: Text.ElideRight }
                Text { objectName: "googleDayTasksEmpty"; anchors.centerIn: parent; visible: parent.count === 0; text: "Aucune tâche pour cette date"; color: "#7896A3" }
            }
        }
        AuraButton { text: "FERMER"; onClicked: popup.close() }
    }
}
