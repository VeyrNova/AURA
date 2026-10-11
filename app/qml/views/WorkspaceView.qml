import QtQuick
import "../components"

Item {
    id: root

    property bool lightMode: false
    property string workspace: "talk"
    property real safeLeft: 18
    property real safeRight: 10

    // AURA_MODULES_NATIVE_FIX30
    signal navigateRequested(string key)
    signal conversationPrefillRequested(string text)
    readonly property real usableWidth: Math.max(320, width - safeLeft - safeRight)

    function titleFor(v) {
        if (v === "talk") return "CONVERSATION"
        if (v === "memory") return "MÉMOIRE"
        if (v === "tasks") return "TÂCHES"
        if (v === "agenda") return "AGENDA"
        if (v === "modules") return "MODULES"
        if (v === "music") return "MUSIQUE"
        if (v === "weather") return "MÉTÉO"
        if (v === "aura-live") return "AURA LIVE"
        if (v === "diagnostics") return "DIAGNOSTICS"
        if (v === "settings") return "PARAMÈTRES"
        return v.toUpperCase()
    }

    ConversationView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "talk"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    MemoryView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "memory"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    TasksView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "tasks"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    AgendaView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "agenda"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    DiagnosticsView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "diagnostics"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    SettingsView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "settings"
        lightMode: root.lightMode

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    ModulesView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "modules"
        lightMode: root.lightMode

        onNavigateRequested: function(key) {
            root.navigateRequested(key)
        }

        onConversationPrefillRequested: function(text) {
            root.conversationPrefillRequested(text)
        }

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
    }

    // AURA_WEATHER_NATIVE_R20
    WeatherView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "weather"
        lightMode: root.lightMode

        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }

    MusicCenterView {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: root.workspace === "music"
        lightMode: root.lightMode

        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }

    // AURA_MUSIC_CENTER_PARITY_FIX35
    GlassPanel {
        x: root.safeLeft
        y: 0
        width: root.usableWidth
        height: root.height
        visible: !["talk", "memory", "tasks", "agenda", "diagnostics", "settings", "modules", "music", "weather"].includes(root.workspace)
        lightMode: root.lightMode
        radius: 18
        accent: root.workspace === "music" ? "#DA5CFF"
              : root.workspace === "aura-live" ? "#A66CFF"
              : "#74EFFF"

        Behavior on x {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on width {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        Column {
            anchors.centerIn: parent
            spacing: 16

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.titleFor(root.workspace)
                color: root.lightMode ? "#15394F" : "#DDF8FF"
                font.pixelSize: 30
                font.weight: Font.Light
                font.letterSpacing: 5
            }

            Text {
                width: 580
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Conversation, Mémoire, Tâches et Agenda sont maintenant raccordés au Core AURA headless. Ce workspace sera migré lors d’une prochaine phase."
                color: root.lightMode ? "#5B788B" : "#6C8799"
                font.pixelSize: 11
                lineHeight: 1.45
            }
        }
    }
}
