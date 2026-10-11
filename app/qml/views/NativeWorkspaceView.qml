import QtQuick
import QtQuick.Controls

Item {
    id: root
    property bool lightMode: false
    property string workspace: "home"
    property real safeLeft: 18
    property real safeRight: 10
    signal navigateRequested(string key)
    signal conversationPrefillRequested(string text)
    readonly property bool conversationWorkspace: root.workspace === "talk" || root.workspace === "conversation"

    readonly property color panel: root.lightMode ? "#EAF4F7" : "#07131E"
    readonly property color card: root.lightMode ? "#DCECF1" : "#0A202D"
    readonly property color card2: root.lightMode ? "#F4FAFC" : "#0C1822"
    readonly property color text0: root.lightMode ? "#17394D" : "#D8F7FF"
    readonly property color text1: root.lightMode ? "#557487" : "#84A8B7"
    readonly property color accent: root.lightMode ? "#2299A8" : "#74EFFF"

    ModulesView {
        objectName: "auraNativeModulesView"
        x: root.safeLeft
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "modules"
        lightMode: root.lightMode
        onNavigateRequested: function(key) { root.navigateRequested(key) }
        onConversationPrefillRequested: function(text) { root.conversationPrefillRequested(text) }
    }

    SettingsView {
        objectName: "auraNativeSettingsView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "settings"
        lightMode: root.lightMode
    }

    MailView {
        objectName: "auraNativeMailView"
        x: root.safeLeft; y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "mail"
        lightMode: root.lightMode
    }
    Loader { objectName: "auraNativeMapsViewLoader"; x: root.safeLeft; y: 0; width: Math.max(320, root.width - root.safeLeft - root.safeRight); height: root.height; active: root.workspace === "maps"; source: "MapsView.qml"; onLoaded: if (item) { item.width = width; item.height = height; item.lightMode = root.lightMode } }

    Loader { objectName: "auraNativeSearchViewLoader"; x: root.safeLeft; y: 0; width: Math.max(320, root.width - root.safeLeft - root.safeRight); height: root.height; active: root.workspace === "search"; source: "SearchView.qml"; onLoaded: if (item) { item.width = width; item.height = height; item.lightMode = root.lightMode } }
    Loader { objectName: "auraNativeDocumentsViewLoader"; x: root.safeLeft; y: 0; width: Math.max(320, root.width - root.safeLeft - root.safeRight); height: root.height; active: root.workspace === "documents"; source: "DocumentsView.qml"; onLoaded: if (item) { item.width = width; item.height = height; item.lightMode = root.lightMode } }
    Loader { objectName: "auraNativeContactsViewLoader"; x: root.safeLeft; y: 0; width: Math.max(320, root.width - root.safeLeft - root.safeRight); height: root.height; active: root.workspace === "contacts"; source: "ContactsView.qml"; onLoaded: if (item) { item.width = width; item.height = height; item.lightMode = root.lightMode } }

    AgendaView {
        objectName: "auraNativeAgendaView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "agenda"
        lightMode: root.lightMode
    }

    TasksView {
        objectName: "auraNativeTasksView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "tasks"
        lightMode: root.lightMode
    }

    DiagnosticsView {
        objectName: "auraNativeDiagnosticsView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "diagnostics" || root.workspace === "diagnostic"
        lightMode: root.lightMode
    }

    WeatherView {
        objectName: "auraNativeWeatherView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "weather" || root.workspace === "meteo" || root.workspace === "météo"
        lightMode: root.lightMode
    }

    MusicCenterView {
        objectName: "auraNativeMusicCenterView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "music"
        lightMode: root.lightMode
    }

    DeveloperFabricView {
        objectName: "auraNativeDeveloperFabricView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "developer" || root.workspace === "developer-fabric" || root.workspace === "adf"
        lightMode: root.lightMode
    }

    MemoryView {
        objectName: "auraPremiumMemoryView"
        x: root.safeLeft
        y: 0
        width: Math.max(320, root.width - root.safeLeft - root.safeRight)
        height: root.height
        visible: root.workspace === "memory" || root.workspace === "memories" || root.workspace === "memoire"
        lightMode: root.lightMode
    }

    Rectangle {
        visible: !root.conversationWorkspace
                 && root.workspace !== "settings"
                 && root.workspace !== "mail"
                 && root.workspace !== "maps"
                 && root.workspace !== "search"
                 && root.workspace !== "documents"
                 && root.workspace !== "contacts"
                 && root.workspace !== "modules"
                 && root.workspace !== "memory"
                 && root.workspace !== "memories"
                 && root.workspace !== "memoire"
                 && root.workspace !== "agenda"
                 && root.workspace !== "tasks"
                 && root.workspace !== "diagnostics"
                 && root.workspace !== "diagnostic"
                 && root.workspace !== "weather"
                 && root.workspace !== "meteo"
                 && root.workspace !== "météo"
                 && root.workspace !== "music"
                 && root.workspace !== "developer"
                 && root.workspace !== "developer-fabric"
                 && root.workspace !== "adf"
        anchors.fill: parent
        radius: 16
        color: root.panel
        border.width: 1
        border.color: root.lightMode ? "#4B7190" : "#1C85A8"

        Column {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 16

            Row {
                width: parent.width
                spacing: 14

                Column {
                    width: parent.width - 190
                    spacing: 5
                    Text {
                        text: root.workspace === "memory" || root.workspace === "memories" || root.workspace === "memoire"
                              ? "AURA NATIVE · MÉMOIRE"
                              : "AURA NATIVE · FOUNDATION"
                        color: root.text0
                        font.pixelSize: 22
                        font.letterSpacing: 2
                    }
                    Text {
                        text: "Workspace: " + root.workspace
                        color: root.text1
                        font.pixelSize: 12
                    }
                }

                Rectangle {
                    width: 176
                    height: 32
                    radius: 8
                    color: root.card
                    border.width: 1
                    border.color: root.accent
                    Text {
                        anchors.centerIn: parent
                        text: "MEMORY · AVAILABLE"
                        color: root.accent
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 178
                radius: 12
                color: root.card
                border.width: 1
                border.color: root.lightMode ? "#5B8B9F" : "#1B6178"

                Column {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text {
                        text: "Ajouter un souvenir explicite"
                        color: root.text0
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    TextArea {
                        id: memoryInput
                        width: parent.width
                        height: 72
                        placeholderText: "Ex. Pour AURA, je préfère une interface très minimaliste..."
                        wrapMode: TextEdit.Wrap
                        color: root.text0
                        placeholderTextColor: root.text1
                    }

                    Row {
                        spacing: 10
                        Button {
                            text: "Enregistrer"
                            enabled: memoryInput.text.trim().length > 0
                            onClicked: {
                                if (coreBridge.createMemory(memoryInput.text)) {
                                    memoryInput.clear()
                                }
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "État · " + coreBridge.memoryStatus
                            color: root.text1
                            font.pixelSize: 11
                        }
                    }
                }
            }

            Row {
                width: parent.width
                spacing: 10

                TextField {
                    id: memorySearch
                    width: parent.width - 224
                    height: 38
                    placeholderText: "Rechercher dans la mémoire locale"
                    color: root.text0
                    placeholderTextColor: root.text1
                    onAccepted: coreBridge.searchMemories(text)
                }

                Button {
                    width: 96
                    text: "Rechercher"
                    onClicked: coreBridge.searchMemories(memorySearch.text)
                }

                Button {
                    width: 108
                    text: "Tout afficher"
                    onClicked: {
                        memorySearch.clear()
                        coreBridge.refreshMemories()
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: Math.max(120, parent.height - 356)
                radius: 12
                color: root.card2
                border.width: 1
                border.color: root.lightMode ? "#6E93A5" : "#173F53"

                ListView {
                    id: memoriesList
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true
                    spacing: 8
                    model: coreBridge.memories

                    header: Text {
                        width: memoriesList.width
                        height: 30
                        text: coreBridge.memoryCount + " souvenir(s) local(aux)"
                        color: root.text1
                        font.pixelSize: 11
                    }

                    delegate: Rectangle {
                        required property var modelData
                        width: memoriesList.width
                        height: Math.max(66, contentText.implicitHeight + 30)
                        radius: 9
                        color: root.card
                        border.width: 1
                        border.color: modelData.is_sensitive
                                      ? (root.lightMode ? "#B77A69" : "#8E5361")
                                      : (root.lightMode ? "#7597A7" : "#28536A")

                        Text {
                            id: contentText
                            anchors.left: parent.left
                            anchors.right: forgetButton.left
                            anchors.top: parent.top
                            anchors.margins: 12
                            anchors.rightMargin: 14
                            text: modelData.content
                            color: root.text0
                            wrapMode: Text.Wrap
                            font.pixelSize: 12
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.leftMargin: 12
                            anchors.bottomMargin: 8
                            text: modelData.memory_type + " · importance " + modelData.importance
                                  + (modelData.is_sensitive ? " · sensible" : "")
                            color: root.text1
                            font.pixelSize: 9
                        }

                        Button {
                            id: forgetButton
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.rightMargin: 10
                            width: 78
                            text: "Oublier"
                            onClicked: coreBridge.forgetMemory(modelData.memory_id)
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: coreBridge.memoryCount === 0
                        text: coreBridge.memoryStatus === "searching"
                              ? "Recherche..."
                              : "Aucun souvenir à afficher."
                        color: root.text1
                        font.pixelSize: 12
                    }
                }
            }

            Row {
                spacing: 8
                Repeater {
                    model: ["conversation · available", "musique · not_migrated", "Google · not_migrated", "météo · not_migrated", "voix · not_migrated", "productivité · not_migrated"]
                    delegate: Rectangle {
                        width: 128
                        height: 26
                        radius: 7
                        color: root.card
                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: root.text1
                            font.pixelSize: 9
                        }
                    }
                }
            }
        }
    }

    NativeConversationView {
        anchors.fill: parent
        visible: root.conversationWorkspace
        lightMode: root.lightMode
        safeLeft: root.safeLeft
        safeRight: root.safeRight
    }

    Component.onCompleted: {
        if (coreBridge.memoryAvailable && (root.workspace === "memory" || root.workspace === "memories" || root.workspace === "memoire")) {
            coreBridge.refreshMemories()
        }
    }
}
