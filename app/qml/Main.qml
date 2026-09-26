import QtQuick
import QtQuick.Controls
import "components"
import "views"

ApplicationWindow {
    id: root

    visible: true
    width: 1536
    height: 960
    minimumWidth: 1180
    minimumHeight: 720
    title: "AURA Native UI POC 6H FIX2"
    color: "transparent"

    flags: bridge.windowedMode
           ? Qt.Window
           : (Qt.Window | Qt.FramelessWindowHint)

    readonly property bool lightMode: bridge.theme === "light"
    readonly property color text0: lightMode ? "#15394F" : "#EFFBFF"
    readonly property color text1: lightMode ? "#557487" : "#68899E"
    readonly property color cyan: lightMode ? "#2AB5C1" : "#74EFFF"

    property int frameCounter: 0
    property bool metricsVisible: false
    property bool modulesDockOpen: false
    property bool musicDockOpen: false
    property bool musicMiniDismissed: false
    // AURA_MUSIC_PIXELPLAYER_EXPERIENCE_FIX36
    // AURA_MUSIC_SUBDOCK_NATIVE_FIX33
    // AURA_MODULES_SUBDOCK_FIX31_R2

    // Global R16 safe-zone metrics.
    // The contextual workspaces must never sit below the dynamic dock.
    readonly property real dockSafeGap: 16
    readonly property real workspaceSafeRight: 10
    readonly property real workspaceSafeLeft: Math.max(
        18,
        liquidDock.x + liquidDock.width + dockSafeGap - workspaceFrame.x
    )
    readonly property real workspaceUsableWidth: Math.max(
        320,
        workspaceFrame.width - workspaceSafeLeft - workspaceSafeRight
    )

    // Everything underneath the liquid overlays lives in this layer.
    Item {
        id: sceneLayer
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: root.lightMode ? "#F5F9FC" : "#02050A"
                }
                GradientStop {
                    position: 0.52
                    color: root.lightMode ? "#EAF2F7" : "#020710"
                }
                GradientStop {
                    position: 1.0
                    color: root.lightMode ? "#DDE9F1" : "#010308"
                }
            }
        }

        Item {
            id: workspaceFrame
            x: 10
            y: 76
            width: parent.width - 20
            height: parent.height - 136

            // Chromium keeps the HERO alive behind contextual workspaces.
            HomeView {
                id: persistentHome
                anchors.fill: parent
                lightMode: root.lightMode
                foregroundHome: bridge.workspace === "home"
            }

            Loader {
                anchors.fill: parent
                active: bridge.workspace !== "home"
                asynchronous: true

                sourceComponent: WorkspaceView {
                    lightMode: root.lightMode
                    workspace: bridge.workspace
                    safeLeft: root.workspaceSafeLeft
                    safeRight: root.workspaceSafeRight

                    // AURA_MODULES_NATIVE_FIX30
                    onNavigateRequested: function(key) {
                        bridge.setWorkspace(key)
                    }

                    onConversationPrefillRequested: function(text) {
                        composer.prefill(text)
                        bridge.setWorkspace("talk")
                    }
                }
            }
        }
    }

    // Chromium HOME reference topbar — measured from supplied 1919x1079 capture.
    GlassPanel {
        id: topbar
        x: 10
        y: 12
        width: parent.width - 20
        height: 54
        radius: 15
        lightMode: root.lightMode
        accent: root.cyan
        z: 90

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onPressed: {
                if (!bridge.windowedMode) root.startSystemMove()
            }
        }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            GlassPanel {
                width: 34
                height: 34
                radius: 17
                lightMode: root.lightMode
                accent: "#74EFFF"

                Image {
                    anchors.centerIn: parent
                    width: 28
                    height: 28
                    source: root.lightMode
                            ? auraAssetBase + "AURA_LOGO_SYMBOL_ARCTIC.svg"
                            : auraAssetBase + "AURA_LOGO_SYMBOL_NEON.svg"
                    fillMode: Image.PreserveAspectFit
                    mipmap: true
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: "AURA"
                    color: root.text0
                    font.family: "Segoe UI Variable"
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    font.letterSpacing: 5.2
                }
                Text {
                    text: "NEURAL OPERATING INTERFACE"
                    color: root.text1
                    font.pixelSize: 7
                    font.letterSpacing: 1.7
                }
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7

            Rectangle {
                width: 94; height: 29; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#8E06111E"
                border.width: 1
                border.color: root.lightMode ? "#3B7899AF" : "#2470D8EB"
                Row {
                    anchors.centerIn: parent
                    spacing: 7
                    Rectangle {
                        width: 6; height: 6; radius: 3
                        color: bridge.state === "SPEAKING" ? "#A66CFF"
                             : bridge.state === "LISTENING" ? "#66FFCA"
                             : root.cyan
                    }
                    Text {
                        text: bridge.state
                        color: root.text0
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.0
                    }
                }
            }

            Rectangle {
                width: 101; height: 29; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#8E06111E"
                border.width: 1
                border.color: root.lightMode ? "#3B7899AF" : "#2470D8EB"
                Text {
                    anchors.centerIn: parent
                    text: "LOCAL RUNTIME"
                    color: root.text1
                    font.pixelSize: 7
                    font.letterSpacing: 0.8
                }
            }

            Rectangle {
                width: 104; height: 29; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#8E06111E"
                border.width: 1
                border.color: root.lightMode ? "#3B7899AF" : "#2470D8EB"
                Row {
                    anchors.centerIn: parent
                    spacing: 5
                    Rectangle { width: 5; height: 5; radius: 3; color: root.cyan }
                    Text { text: "ROUTER"; color: root.text0; font.pixelSize: 7; font.weight: Font.DemiBold; font.letterSpacing: 0.7 }
                    Text { text: "LOCAL UI"; color: root.text1; font.pixelSize: 6 }
                }
            }

            Rectangle {
                width: 70; height: 29; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#8E06111E"
                border.width: 1
                border.color: root.lightMode ? "#3B7899AF" : "#2470D8EB"
                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "◷"; color: root.cyan; font.pixelSize: 10 }
                    Text {
                        text: bridge.clockText.split(" · ")[0]
                        color: root.text0
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 11
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7

            Rectangle {
                width: 78; height: 28; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#7E06111E"
                border.width: 1
                border.color: root.lightMode ? "#337799AE" : "#1F6ED7EA"
                Text {
                    anchors.centerIn: parent
                    text: root.lightMode ? "MODE SOMBRE" : "MODE CLAIR"
                    color: root.text1
                    font.pixelSize: 7
                    font.letterSpacing: 0.7
                }
                TapHandler { onTapped: bridge.toggleTheme() }
            }

            Rectangle {
                width: 82; height: 28; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#7E06111E"
                border.width: 1
                border.color: root.lightMode ? "#337799AE" : "#1F6ED7EA"
                Text {
                    anchors.centerIn: parent
                    text: coreBridge.connected
                          ? (coreBridge.interactionReady ? "CORE · LINKED" : "CORE · SYNC")
                          : "CORE · OFFLINE"
                    color: root.text1
                    font.pixelSize: 7
                    font.letterSpacing: 0.8
                }
            }

            Rectangle {
                width: 100; height: 28; radius: 8
                color: root.lightMode ? "#EFF8FBFD" : "#7E06111E"
                border.width: 1
                border.color: root.lightMode ? "#337799AE" : "#1F6ED7EA"
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: "CAMILLA · " + coreBridge.voiceStatus.toUpperCase()
                    color: root.text1
                    font.pixelSize: 7
                    font.letterSpacing: 0.6
                }
            }

            Rectangle {
                width: 29; height: 29; radius: 8
                color: "#4B2A0814"
                border.width: 1
                border.color: "#5AFF6C8D"
                Text { anchors.centerIn: parent; text: "⏻"; color: "#FF7798"; font.pixelSize: 13 }
                TapHandler { onTapped: Qt.quit() }
            }
        }
    }

    LiquidDock {
        id: liquidDock
        x: 14
        y: Math.round((root.height - height) / 2)
        backdropSource: sceneLayer
        lightMode: root.lightMode
        workspace: bridge.workspace
        modulesOpen: root.modulesDockOpen
        musicOpen: root.musicDockOpen
        z: 100

        onNavigate: function(key) {
            root.modulesDockOpen = false
            root.musicDockOpen = false
            bridge.setWorkspace(key)
        }

        onExpandedChangedFromUi: function(value) {
            bridge.setDockExpanded(value)
        }
    
        onToggleModulesRequested: function() {
            root.musicDockOpen = false
            if (bridge.workspace === "modules")
                bridge.setWorkspace("home")
            root.modulesDockOpen = !root.modulesDockOpen
            if (root.modulesDockOpen)
                modulesSubdock.page = "modules"
        }

        onToggleMusicRequested: function() {
            root.modulesDockOpen = false
            if (bridge.workspace === "music")
                bridge.setWorkspace("home")
            root.musicDockOpen = !root.musicDockOpen
            if (root.musicDockOpen)
                musicBridge.refresh()
        }
}

        MusicSubdock {
        id: musicSubdock

        // AURA_NATIVE_MUSIC_MINIPLAYER_SAFEZONE_R14 START
        // Adaptive safe-zone geometry. Prefer the dock right side, then left.
        // If neither side fits, move above the dock/composer instead of overlapping.
        readonly property real r14Gap: 12
        readonly property real r14Edge: 18
        readonly property real r14RightX: liquidDock.x + liquidDock.width + r14Gap
        readonly property real r14LeftX: liquidDock.x - width - r14Gap
        readonly property bool r14RightFits: r14RightX + width <= root.width - r14Edge
        readonly property bool r14LeftFits: r14LeftX >= r14Edge
        readonly property bool r14SideFits: r14RightFits || r14LeftFits
        readonly property real r14CenteredX: Math.max(
            r14Edge,
            Math.min(root.width - width - r14Edge, (root.width - width) / 2)
        )
        readonly property real r14NormalY: Math.max(
            82,
            Math.min(
                root.height - height - 78,
                composer.y - height - r14Gap
            )
        )
        readonly property real r14FallbackY: Math.max(
            82,
            Math.min(
                r14NormalY,
                liquidDock.y - height - r14Gap
            )
        )
        readonly property bool r14ShouldShow: bridge.workspace !== "music"
                                              && musicBridge.currentId.length > 0
                                              && !root.musicMiniDismissed

        x: r14RightFits
           ? r14RightX
           : (r14LeftFits ? r14LeftX : r14CenteredX)
        y: r14SideFits ? r14NormalY : r14FallbackY

        enabled: r14ShouldShow
        opacity: r14ShouldShow ? 1.0 : 0.0
        visible: opacity > 0.01

        Behavior on x {
            NumberAnimation { duration: 190; easing.type: Easing.OutCubic }
        }
        Behavior on y {
            NumberAnimation { duration: 190; easing.type: Easing.OutCubic }
        }
        Behavior on opacity {
            NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
        }
        // AURA_NATIVE_MUSIC_MINIPLAYER_SAFEZONE_R14 END

        lightMode: root.lightMode
        backdropSource: sceneLayer
        z: 106

        onCloseRequested: root.musicMiniDismissed = true

        onOpenFullRequested: {
            root.musicMiniDismissed = false
            bridge.setWorkspace("music")
        }
    }


    ModulesSubdock {
        // AURA_MODULES_LIQUID_GLASS_PREMIUM_FIX32
        id: modulesSubdock
        x: liquidDock.x + liquidDock.width + 12
        y: Math.max(82, Math.min(root.height - height - 82, liquidDock.y + 230 - height / 2))
        visible: root.modulesDockOpen
        lightMode: root.lightMode
        backdropSource: sceneLayer
        z: 105
        onNavigateRequested: function(key) { root.modulesDockOpen = false; bridge.setWorkspace(key) }
        onPrefillRequested: function(text) { root.modulesDockOpen = false; composer.prefill(text); bridge.setWorkspace("talk") }
        onCloseRequested: root.modulesDockOpen = false
    }


    Connections {
        target: musicBridge

        function onTrackChanged() {
            if (musicBridge.currentId.length > 0) {
                root.musicMiniDismissed = false
            }
        }
    }

    Composer {
        id: composer
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        backdropSource: sceneLayer
        lightMode: root.lightMode
        z: 110
    }

    // Debug metrics are intentionally NOT part of HOME.
    // F8 shows a compact floating diagnostic only when requested.
    GlassPanel {
        visible: root.metricsVisible
        width: 252
        height: 164
        anchors.right: parent.right
        anchors.rightMargin: 18
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 72
        z: 200
        lightMode: root.lightMode
        accent: "#A66CFF"

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 9

            Text {
                text: "NATIVE BENCHMARK"
                color: root.text0
                font.pixelSize: 10
                font.letterSpacing: 1.7
            }
            Text {
                text: "FPS                 " + bridge.fps
                color: root.text1
                font.pixelSize: 10
            }
            Text {
                text: "Process CPU     " + bridge.cpuPercent.toFixed(2) + " %"
                color: root.text1
                font.pixelSize: 10
            }
            Text {
                text: "RAM RSS          " + bridge.memoryMb.toFixed(1) + " MB"
                color: root.text1
                font.pixelSize: 10
            }
            Text {
                text: "CPU système   " + bridge.systemCpu.toFixed(1) + " %"
                color: root.text1
                font.pixelSize: 10
            }
            Text {
                text: "Orb target       " + bridge.orbTargetFps + " FPS"
                color: root.text1
                font.pixelSize: 10
            }
        }
    }

    FrameAnimation {
        running: true
        onTriggered: root.frameCounter++
    }

    Timer {
        interval: 1000
        repeat: true
        running: true

        onTriggered: {
            bridge.reportFps(root.frameCounter)
            root.frameCounter = 0
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: bridge.setWorkspace("home")
    }
    Shortcut {
        sequence: "Ctrl+L"
        onActivated: bridge.toggleTheme()
    }
    Shortcut {
        sequence: "F8"
        onActivated: root.metricsVisible = !root.metricsVisible
    }
    Shortcut {
        sequence: "F11"
        onActivated: root.visibility =
                     root.visibility === Window.FullScreen
                     ? Window.Windowed
                     : Window.FullScreen
    }
}
