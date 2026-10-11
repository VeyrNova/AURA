import QtQuick
import QtQuick.Effects

Item {
    id: root
    // AURA_DOCK_LABEL_REVEAL_FIX14

    property string iconName: "home"
    property string label: ""
    property bool active: false
    property bool lightMode: false
    property bool dockOpen: false
    property real hoverShift: hover.hovered ? 1 : 0
    signal clicked()

    width: parent ? parent.width : 46
    height: 40

    Rectangle {
        anchors.fill: parent
        radius: 13

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: root.active
                       ? (root.lightMode ? "#7AE4F2F7" : "#267AE4FF")
                       : (hover.hovered
                          ? (root.lightMode ? "#38FFFFFF" : "#0BFFFFFF")
                          : "transparent")
            }
            GradientStop {
                position: 1.0
                color: root.active
                       ? (root.lightMode ? "#64D7EEF6" : "#1A7EB4FF")
                       : "transparent"
            }
        }

        border.width: (root.active || hover.hovered) ? 1 : 0
        border.color: root.active
                      ? (root.lightMode ? "#486DA6BF" : "#387EE8FF")
                      : (root.lightMode ? "#266A9AB3" : "#1F7EE8FF")
    }

    Image {
        id: iconImage
        width: 18
        height: 18
        x: (root.dockOpen ? 14 : (root.width - width) / 2) + root.hoverShift
        anchors.verticalCenter: parent.verticalCenter
        source: auraAssetBase
                + "dock-" + root.iconName
                + (root.lightMode ? "-light.svg" : "-dark.svg")
        fillMode: Image.PreserveAspectFit
        mipmap: true
        opacity: root.active ? 1.0 : 0.82

        Behavior on x {
            NumberAnimation {
                duration: 230
                easing.type: Easing.OutCubic
            }
        }

        MultiEffect {
            anchors.fill: parent
            source: iconImage
            shadowEnabled: root.active || hover.hovered
            shadowColor: root.lightMode ? "#4C4AA6C2" : "#805FE1FF"
            shadowBlur: 0.85
            shadowOpacity: root.active ? 0.72 : 0.40
            visible: root.active || hover.hovered
        }
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 48 + root.hoverShift
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter

        text: root.label
        color: root.lightMode ? "#244E67" : "#EAFBFF"
        font.family: "Segoe UI Variable"
        font.pixelSize: 11
        font.weight: Font.Medium
        font.letterSpacing: 0.25
        elide: Text.ElideRight

        opacity: root.dockOpen ? 0.96 : 0.0
        visible: root.dockOpen || opacity > 0.01
        x: root.dockOpen ? 0 : -7

        Behavior on opacity {
            NumberAnimation { duration: 90 }
        }
        Behavior on x {
            NumberAnimation {
                duration: 140
                easing.type: Easing.OutCubic
            }
        }
    }

    HoverHandler {
        id: hover
    }

    TapHandler {
        onTapped: root.clicked()
    }
}
