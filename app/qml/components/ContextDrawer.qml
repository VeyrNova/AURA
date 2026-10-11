import QtQuick
import QtQuick.Controls

GlassPanel {
    id: root
    property string titleText: ""
    property string subtitleText: ""
    property string accentColor: "#74EFFF"
    property int drawerWidth: 560
    property bool premiumSurface: false
    property int headerHeight: 68
    property int titlePixelSize: 13
    property int subtitlePixelSize: 9
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX26
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX27

    readonly property real edgeGap: 16
    readonly property real minimumDrawerWidth: 360

    width: parent
           ? Math.max(
                 Math.min(minimumDrawerWidth, parent.width - edgeGap * 2),
                 Math.min(drawerWidth, parent.width - edgeGap * 2)
             )
           : drawerWidth
    height: parent ? Math.max(320, parent.height - edgeGap * 2) : 600
    x: edgeGap
    y: edgeGap

    Behavior on width {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }
    radius: 22
    accent: accentColor

    Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        radius: 20
        color: root.premiumSurface
               ? (root.lightMode ? "#E8F9FCFD" : "#D70A1724")
               : (root.lightMode ? "#D9F9FCFD" : "#C60A141F")
        border.width: root.premiumSurface ? 1 : 0
        border.color: root.lightMode ? "#467FA0B2" : "#4C74EFFF"
    }

    Rectangle {
        visible: root.premiumSurface
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.headerHeight + 34
        radius: 20
        opacity: root.lightMode ? 0.54 : 0.92
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.lightMode ? "#68FFFFFF" : "#571A5870" }
            GradientStop { position: 0.46; color: root.lightMode ? "#22E9F9FC" : "#28103448" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    Rectangle {
        visible: root.premiumSurface
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width * 0.58
        height: 2
        radius: 1
        color: root.accentColor
        opacity: 0.88
    }

    Rectangle {
        visible: root.premiumSurface
        anchors.left: parent.left
        anchors.leftMargin: 1
        anchors.top: parent.top
        anchors.topMargin: root.headerHeight + 10
        width: 1
        height: parent.height * 0.42
        color: root.accentColor
        opacity: 0.30
    }

    Rectangle {
        visible: root.premiumSurface
        anchors.fill: parent
        anchors.margins: 5
        radius: 17
        color: "transparent"
        border.width: 1
        border.color: root.lightMode ? "#245A8BA1" : "#173C8DA4"
        opacity: 0.88
    }

    Rectangle {
        visible: root.premiumSurface
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 2
        height: 96
        radius: 18
        opacity: 0.42
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: root.lightMode ? "#1259D4DD" : "#24154145" }
        }
    }

    property alias contentItem: body
    property alias headerActions: actions

    Row {
        id: head
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.headerHeight
        anchors.leftMargin: 22
        anchors.rightMargin: 18

        Column {
            width: parent.width - actions.width
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Text {
                text: root.titleText
                color: root.lightMode ? "#174155" : "#D8F9FF"
                font.pixelSize: root.titlePixelSize
                font.weight: Font.DemiBold
                font.letterSpacing: 2.4
            }
            Text {
                text: root.subtitleText
                color: root.lightMode ? "#698291" : "#789BAC"
                font.pixelSize: root.subtitlePixelSize
            }
        }

        Row {
            id: actions
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: head.bottom
        height: 1
        color: root.premiumSurface
               ? (root.lightMode ? "#3A678EA2" : "#3774EFFF")
               : (root.lightMode ? "#245A8296" : "#1767D3EA")
    }

    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: head.bottom
        anchors.bottom: parent.bottom
        anchors.topMargin: 1
    }
}
