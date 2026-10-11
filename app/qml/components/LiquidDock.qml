import QtQuick

Item {
    id: root
    clip: false

    property Item backdropSource: null
    property bool lightMode: false
    property string workspace: "home"
    property bool modulesOpen: false
    property bool musicOpen: false
    property bool expanded: hover.hovered || focusProxy.activeFocus
    // AURA_DOCK_EXPANSION_STABILITY_FIX14
    // Do not reveal labels while the 60 -> 218 px expansion is still in flight.
    readonly property bool labelsReady: expanded && width >= 176
    property real lensX: 0.50
    property real lensY: 0.36
    signal navigate(string key)
    signal toggleModulesRequested()
    signal toggleMusicRequested()
    // AURA_MUSIC_PIXELPLAYER_EXPERIENCE_FIX36
    // AURA_MUSIC_SUBDOCK_NATIVE_FIX33
    // AURA_MODULES_SUBDOCK_FIX31_R2
    signal expandedChangedFromUi(bool value)

    width: expanded ? 218 : 60
    height: 461

    Behavior on width {
        NumberAnimation {
            duration: 180
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.16, 0.85, 0.18, 1.0, 1.0, 1.0]
        }
    }

    LiquidGlass {
        anchors.fill: parent
        backdropSource: root.backdropSource
        sourceX: root.x
        sourceY: root.y
        lightMode: root.lightMode
        cornerRadius: 20
        blurStrength: 0.78
        saturationBoost: 0.20
        lensX: root.lensX
        lensY: root.lensY
    }

    FocusScope {
        id: focusProxy
        anchors.fill: parent
        focus: false
    }

    HoverHandler {
        id: hover
        onHoveredChanged: {
            root.expandedChangedFromUi(root.expanded)
            if (!hovered) {
                root.lensX = 0.50
                root.lensY = 0.36
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        z: 0

        onPositionChanged: function(mouse) {
            root.lensX = Math.max(0, Math.min(1, mouse.x / Math.max(1, width)))
            root.lensY = Math.max(0, Math.min(1, mouse.y / Math.max(1, height)))
        }

        onExited: {
            root.lensX = 0.50
            root.lensY = 0.36
        }
    }

    Column {
        anchors.fill: parent
        anchors.margins: root.expanded ? 9 : 7
        spacing: 5

        Behavior on anchors.margins {
            NumberAnimation { duration: 150 }
        }

        DockButton {
            iconName: "home"
            label: "Accueil"
            active: root.workspace === "home"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("home")
        }
        DockButton {
            iconName: "conversation"
            label: "Conversation"
            active: root.workspace === "talk"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("talk")
        }
        DockButton {
            iconName: "memory"
            label: "Mémoire"
            active: root.workspace === "memory"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("memory")
        }
        DockButton {
            iconName: "tasks"
            label: "Tâches"
            active: root.workspace === "tasks"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("tasks")
        }
        DockButton {
            iconName: "agenda"
            label: "Agenda"
            active: root.workspace === "agenda"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("agenda")
        }
        DockButton {
            iconName: "modules"
            label: "Modules"
            active: root.modulesOpen || root.workspace === "modules"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.toggleModulesRequested()
        }
        DockButton {
            iconName: "music"
            label: "Musique"
            active: root.workspace === "music"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("music")
        }
        DockButton {
            iconName: "aura-live"
            label: "AURA Live"
            active: root.workspace === "aura-live"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("aura-live")
        }
        DockButton {
            iconName: "diagnostics"
            label: "Diagnostics"
            active: root.workspace === "diagnostics"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("diagnostics")
        }
        DockButton {
            iconName: "settings"
            label: "Paramètres"
            active: root.workspace === "settings"
            lightMode: root.lightMode
            dockOpen: root.labelsReady
            onClicked: root.navigate("settings")
        }
    }
}
