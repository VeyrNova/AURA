import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "../components"

Item {
    id: root

    // AURA_MUSIC_PIXELPLAYER_PREMIUM_FIX40
    property bool lightMode: false
    property string page: "home"
    property string libraryQuery: ""
    property string librarySort: "playlist"
    property bool favoritesOnly: false
    property bool duplicatesOnly: false
    property string selectedCollectionId: ""

    property color cyan: "#74EFFF"
    property color purple: "#A66CFF"
    property color ink: lightMode ? "#EEF8FB" : "#050B13"
    property color textPrimary: lightMode ? "#173F56" : "#F3FDFF"
    property color textSecondary: lightMode ? "#607C8D" : "#7896A7"
    property color surface: lightMode ? "#D8FFFFFF" : "#6A07131F"
    property color surfaceSoft: lightMode ? "#BFFFFFFF" : "#4207111C"
    property color stroke: lightMode ? "#355F8298" : "#2F64809A"

    function asset(name) {
        return auraAssetBase + name
    }

    function applyLibraryFilter() {
        musicBridge.setLibraryView(
            libraryQuery,
            librarySort,
            favoritesOnly,
            duplicatesOnly
        )
    }

    function navLabel(key) {
        if (key === "home") return "ACCUEIL"
        if (key === "player") return "LECTURE"
        if (key === "library") return "BIBLIOTHÈQUE"
        if (key === "queue") return "FILE"
        if (key === "playlists") return "PLAYLISTS"
        return "HISTORIQUE"
    }

    function navIcon(key) {
        if (key === "home") return asset("music-nav-home.svg")
        if (key === "player") return asset("music-nav-player.svg")
        if (key === "library") return asset("music-nav-library.svg")
        if (key === "queue") return asset("music-nav-queue.svg")
        if (key === "playlists") return asset("music-nav-playlists.svg")
        return asset("music-nav-history.svg")
    }

    Component.onCompleted: {
        musicBridge.refreshAll()
        applyLibraryFilter()
    }

    // Immersive PixelPlayer-inspired desktop canvas.
    Rectangle {
        anchors.fill: parent
        radius: 28
        color: root.lightMode ? "#EEF9FC" : "#050B13"
        clip: true

        // Cover-art ambience. This is deliberately subtle so text remains readable.
        Image {
            id: ambientCover
            anchors.fill: parent
            source: musicBridge.currentCover
            visible: musicBridge.currentCover.length > 0
            fillMode: Image.PreserveAspectCrop
            opacity: root.lightMode ? 0.08 : 0.14
            smooth: true
            mipmap: true
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop {
                    position: 0.0
                    color: root.lightMode ? "#EAF9FC" : "#E9051420"
                }
                GradientStop {
                    position: 0.48
                    color: root.lightMode ? "#F5FBFD" : "#F0060D17"
                }
                GradientStop {
                    position: 1.0
                    color: root.lightMode ? "#EEEAF8" : "#E90E0A21"
                }
            }
        }

        Rectangle {
            width: parent.width * 0.42
            height: width
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.leftMargin: -parent.width * 0.15
            anchors.bottomMargin: -parent.width * 0.23
            radius: width / 2
            color: root.lightMode ? "#0A74EFFF" : "#1833CDEB"
            opacity: 0.34
        }

        Rectangle {
            width: parent.width * 0.34
            height: width
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: -parent.width * 0.11
            anchors.topMargin: -parent.width * 0.14
            radius: width / 2
            color: root.lightMode ? "#0BA66CFF" : "#1C7024AC"
            opacity: 0.32
        }

        // -----------------------------------------------------------------
        // Header
        // -----------------------------------------------------------------
        Row {
            id: header
            x: 26
            y: 18
            width: parent.width - 52
            height: 54
            spacing: 12

            Column {
                width: parent.width - 260
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3

                Text {
                    text: "AURA MUSIC"
                    color: root.textPrimary
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    font.letterSpacing: 2.8
                }

                Text {
                    text: "PIXEL-INSPIRED · LOCAL MUSIC · IMMERSIVE"
                    color: root.textSecondary
                    font.pixelSize: 8
                    font.letterSpacing: 0.8
                }
            }

            Rectangle {
                width: 116
                height: 32
                radius: 16
                anchors.verticalCenter: parent.verticalCenter
                color: root.surfaceSoft
                border.width: 1
                border.color: musicBridge.available ? "#4374EFFF" : "#55FF789A"

                Row {
                    anchors.centerIn: parent
                    spacing: 6

                    Rectangle {
                        width: 7
                        height: 7
                        radius: 4
                        color: musicBridge.available ? root.cyan : "#FF789A"
                    }

                    Text {
                        text: musicBridge.available ? "VLC CONNECTÉ" : "VLC OFFLINE"
                        color: musicBridge.available ? "#BFF8FF" : "#FF9BAD"
                        font.pixelSize: 7
                        font.weight: Font.DemiBold
                    }
                }
            }

            Rectangle {
                width: 104
                height: 32
                radius: 16
                anchors.verticalCenter: parent.verticalCenter
                color: refreshHover.hovered ? "#2B74EFFF" : root.surfaceSoft
                border.width: 1
                border.color: "#3D74EFFF"

                Text {
                    anchors.centerIn: parent
                    text: "ACTUALISER"
                    color: "#C5F8FF"
                    font.pixelSize: 7
                    font.weight: Font.DemiBold
                }

                HoverHandler {
                    id: refreshHover
                }

                TapHandler {
                    onTapped: musicBridge.refreshAll()
                }
            }
        }

        Rectangle {
            x: 26
            y: header.y + header.height + 4
            width: parent.width - 52
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#0074EFFF" }
                GradientStop { position: 0.35; color: "#4E74EFFF" }
                GradientStop { position: 0.72; color: "#4EA66CFF" }
                GradientStop { position: 1.0; color: "#00A66CFF" }
            }
        }

        Item {
            id: content
            x: 26
            y: 88
            width: parent.width - 52
            height: parent.height - 178

            // =============================================================
            // HOME / YOUR MIX
            // =============================================================
            Item {
                visible: root.page === "home"
                anchors.fill: parent

                Row {
                    anchors.fill: parent
                    spacing: 24

                    Item {
                        width: parent.width * 0.43
                        height: parent.height

                        Column {
                            anchors.fill: parent
                            spacing: 8

                            Text {
                                text: "VOTRE"
                                color: root.textPrimary
                                font.pixelSize: 34
                                font.weight: Font.DemiBold
                                font.letterSpacing: -0.4
                            }

                            Text {
                                text: "MIX"
                                color: root.cyan
                                font.pixelSize: 48
                                font.weight: Font.DemiBold
                                font.letterSpacing: -1.0
                            }

                            Text {
                                text: "Votre musique locale, réinventée par AURA"
                                color: root.textSecondary
                                font.pixelSize: 8
                            }

                            Item {
                                id: collage
                                width: parent.width
                                height: parent.height - 128

                                Repeater {
                                    model: musicLibraryModel

                                    Rectangle {
                                        required property int index
                                        required property string itemId
                                        required property string title
                                        required property string artist
                                        required property string coverDataUri

                                        visible: index < 5

                                        width: index === 0 ? 210
                                             : index === 1 ? 128
                                             : index === 2 ? 112
                                             : index === 3 ? 96
                                             : 86
                                        height: width
                                        radius: width / 2

                                        x: index === 0 ? collage.width * 0.27
                                         : index === 1 ? collage.width * 0.03
                                         : index === 2 ? collage.width * 0.68
                                         : index === 3 ? collage.width * 0.03
                                         : collage.width * 0.72

                                        y: index === 0 ? collage.height * 0.19
                                         : index === 1 ? collage.height * 0.07
                                         : index === 2 ? collage.height * 0.04
                                         : index === 3 ? collage.height * 0.60
                                         : collage.height * 0.63

                                        color: "#71091420"
                                        border.width: musicBridge.currentId === itemId ? 3 : 1
                                        border.color: musicBridge.currentId === itemId
                                                      ? root.cyan
                                                      : "#4D7792A8"
                                        clip: true

                                        Image {
                                            id: auraR8Art1
                                            anchors.fill: parent
                                            anchors.margins: coverDataUri.length ? 0 : width * 0.30
                                            source: coverDataUri.length
                                                    ? coverDataUri
                                                    : root.asset("music-note-premium.svg")
                                            fillMode: coverDataUri.length
                                                      ? Image.PreserveAspectCrop
                                                      : Image.PreserveAspectFit
                                            smooth: true
                                            mipmap: true
                                        
                                            // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 real mask
                                            layer.enabled: true
                                            layer.effect: MultiEffect {
                                                maskEnabled: true
                                                maskSource: ShaderEffectSource {
                                                    sourceItem: Rectangle {
                                                        width: auraR8Art1.width
                                                        height: auraR8Art1.height
                                                        radius: Math.min(auraR8Art1.width, auraR8Art1.height) / 2
                                                        color: "white"
                                                    }
                                                }
                                            }


                                            // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 START
                                            // Full-surface glass only: no pill-shaped highlight bars.
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Math.min(auraR8Art1.width, auraR8Art1.height) / 2
                                                z: 20
                                                opacity: 0.34
                                                gradient: Gradient {
                                                    GradientStop { position: 0.00; color: "#12FFFFFF" }
                                                    GradientStop { position: 0.30; color: "#035FDFFF" }
                                                    GradientStop { position: 0.68; color: "#00000000" }
                                                    GradientStop { position: 1.00; color: "#064A35FF" }
                                                }
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: Math.max(0, (Math.min(auraR8Art1.width, auraR8Art1.height) / 2) - 2)
                                                color: "transparent"
                                                border.width: 1
                                                border.color: "#E9FBFF"
                                                opacity: 0.15
                                                z: 21
                                            }
                                            // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 END


                                            // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 START
                                            // SAFE hover polish: opacity only. No scale/transform on layered Image.
                                            HoverHandler {
                                                id: auraR8Art1HoverSafe
                                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: Math.max(0, (Math.min(auraR8Art1.width, auraR8Art1.height) / 2) - 2)
                                                color: "transparent"
                                                border.width: 1
                                                border.color: "#79ECFF"
                                                opacity: auraR8Art1HoverSafe.hovered ? 0.42 : 0.0
                                                z: 44
                                                Behavior on opacity {
                                                    NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                                                }
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Math.min(auraR8Art1.width, auraR8Art1.height) / 2
                                                color: "#126D4CFF"
                                                opacity: auraR8Art1HoverSafe.hovered ? 0.12 : 0.0
                                                z: 43
                                                Behavior on opacity {
                                                    NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                                }
                                            }
                                            // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 END
}
                                        // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 glass rings
                                        Rectangle {
                                            anchors.fill: auraR8Art1
                                            anchors.margins: -4
                                            radius: (Math.min(auraR8Art1.width, auraR8Art1.height) / 2) + 4
                                            color: "transparent"
                                            border.width: 1
                                            border.color: "#A06BFF"
                                            opacity: 0.34
                                            z: auraR8Art1.z + 1
                                        }
                                        Rectangle {
                                            anchors.fill: auraR8Art1
                                            radius: Math.min(auraR8Art1.width, auraR8Art1.height) / 2
                                            color: "transparent"
                                            border.width: 1
                                            border.color: "#67E8FF"
                                            opacity: 0.72
                                            z: auraR8Art1.z + 3
                                        }
                                        Rectangle {
                                            anchors.fill: auraR8Art1
                                            radius: Math.min(auraR8Art1.width, auraR8Art1.height) / 2
                                            opacity: 0.72
                                            z: auraR8Art1.z + 2
                                            gradient: Gradient {
                                                GradientStop { position: 0.00; color: "#20FFFFFF" }
                                                GradientStop { position: 0.34; color: "#05FFFFFF" }
                                                GradientStop { position: 0.72; color: "#00000000" }
                                                GradientStop { position: 1.00; color: "#12030A18" }
                                            }
                                        }


                                        Rectangle {
                                            anchors.fill: parent
                                            radius: width / 2
                                            color: mixHover.hovered ? "#1AFFFFFF" : "transparent"
                                        }

                                        HoverHandler {
                                            id: mixHover
                                        }

                                        TapHandler {
                                            onDoubleTapped: musicBridge.playId(itemId)
                                        }
                                    }
                                }

                                Rectangle {
                                    width: 76
                                    height: 76
                                    radius: 38
                                    anchors.centerIn: parent
                                    color: mixPlayHover.hovered ? "#B574EFFF" : "#9274EFFF"
                                    border.width: 2
                                    border.color: "#63A66CFF"

                                    Image {
                                        anchors.centerIn: parent
                                        width: 30
                                        height: 30
                                        source: root.asset(
                                            musicBridge.playing
                                            ? "music-pause-premium.svg"
                                            : "music-play-premium.svg"
                                        )
                                        fillMode: Image.PreserveAspectFit
                                    }

                                    HoverHandler {
                                        id: mixPlayHover
                                    }

                                    TapHandler {
                                        onTapped: {
                                            if (musicBridge.currentId.length) {
                                                musicBridge.togglePlay()
                                            } else if (musicBridge.playlistCount > 0) {
                                                musicBridge.playIndex(0)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        width: parent.width * 0.57 - 24
                        height: parent.height

                        Column {
                            anchors.fill: parent
                            spacing: 14

                            Rectangle {
                                visible: musicBridge.resumeEligible
                                width: parent.width
                                height: 78
                                radius: 22
                                color: root.surface
                                border.width: 1
                                border.color: "#4E74EFFF"

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 10

                                    Column {
                                        width: parent.width - 190
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 3

                                        Text {
                                            text: "REPRENDRE"
                                            color: root.cyan
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                            font.letterSpacing: 1.0
                                        }

                                        Text {
                                            width: parent.width
                                            text: musicBridge.resumeTitle
                                            color: root.textPrimary
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: musicBridge.resumePositionLabel
                                            color: root.textSecondary
                                            font.pixelSize: 7
                                        }
                                    }

                                    Rectangle {
                                        width: 90
                                        height: 34
                                        radius: 17
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: "#3774EFFF"
                                        border.width: 1
                                        border.color: root.cyan

                                        Text {
                                            anchors.centerIn: parent
                                            text: "REPRENDRE"
                                            color: "#E7FCFF"
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }

                                        TapHandler {
                                            onTapped: musicBridge.resumePlayback()
                                        }
                                    }

                                    Rectangle {
                                        width: 70
                                        height: 34
                                        radius: 17
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: "#3707131F"
                                        border.width: 1
                                        border.color: "#4A875D78"

                                        Text {
                                            anchors.centerIn: parent
                                            text: "OUBLIER"
                                            color: "#B88D9A"
                                            font.pixelSize: 7
                                        }

                                        TapHandler {
                                            onTapped: musicBridge.clearResume()
                                        }
                                    }
                                }
                            }

                            Text {
                                text: "VOTRE ESPACE"
                                color: root.textPrimary
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.3
                            }

                            Row {
                                width: parent.width
                                spacing: 10

                                Repeater {
                                    model: [
                                        { key: "library", label: "BIBLIOTHÈQUE", value: musicBridge.playlistCount + " titres", icon: "music-nav-library.svg" },
                                        { key: "queue", label: "FILE", value: "Lecture continue", icon: "music-nav-queue.svg" },
                                        { key: "playlists", label: "PLAYLISTS", value: musicBridge.collections.length + " listes", icon: "music-nav-playlists.svg" }
                                    ]

                                    Rectangle {
                                        required property var modelData
                                        width: (parent.width - 20) / 3
                                        height: 96
                                        radius: 24
                                        color: spaceHover.hovered ? "#7B0C1B2A" : root.surfaceSoft
                                        border.width: 1
                                        border.color: spaceHover.hovered ? root.cyan : root.stroke

                                        Image {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 15
                                            width: 27
                                            height: 27
                                            source: root.asset(modelData.icon)
                                            fillMode: Image.PreserveAspectFit
                                        }

                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 51
                                            text: modelData.label
                                            color: root.textPrimary
                                            font.pixelSize: 8
                                            font.weight: Font.DemiBold
                                        }

                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 69
                                            text: modelData.value
                                            color: root.textSecondary
                                            font.pixelSize: 7
                                        }

                                        HoverHandler {
                                            id: spaceHover
                                        }

                                        TapHandler {
                                            onTapped: {
                                                root.page = modelData.key
                                                if (root.page === "library")
                                                    root.applyLibraryFilter()
                                                if (root.page === "playlists")
                                                    musicBridge.refreshCollections()
                                            }
                                        }
                                    }
                                }
                            }

                            Row {
                                width: parent.width

                                Text {
                                    width: parent.width - 100
                                    text: "RÉCEMMENT ÉCOUTÉS"
                                    color: root.textPrimary
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                }

                                Text {
                                    width: 100
                                    horizontalAlignment: Text.AlignRight
                                    text: "HISTORIQUE ›"
                                    color: root.purple
                                    font.pixelSize: 7

                                    TapHandler {
                                        onTapped: root.page = "history"
                                    }
                                }
                            }

                            ListView {
                                width: parent.width
                                height: parent.height - y
                                clip: true
                                spacing: 6
                                model: musicLibraryModel

                                delegate: Rectangle {
                                    required property int index
                                    required property string itemId
                                    required property string title
                                    required property string artist
                                    required property string album
                                    required property string coverDataUri
                                    required property bool favorite

                                    visible: index < 9
                                    width: ListView.view.width
                                    height: visible ? 52 : 0
                                    radius: 18
                                    color: recentHover.hovered ? "#570C1A27" : "transparent"

                                    Rectangle {
                                        x: 6
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 40
                                        height: 40
                                        radius: 12
                                        color: "#6B0A1521"
                                        clip: true

                                        Image {
                                            id: auraR8Art2
                                            anchors.fill: parent
                                            anchors.margins: coverDataUri.length ? 0 : 10
                                            source: coverDataUri.length
                                                    ? coverDataUri
                                                    : root.asset("music-note-premium.svg")
                                            fillMode: coverDataUri.length
                                                      ? Image.PreserveAspectCrop
                                                      : Image.PreserveAspectFit
                                        
                                            // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 real mask
                                            layer.enabled: true
                                            layer.effect: MultiEffect {
                                                maskEnabled: true
                                                maskSource: ShaderEffectSource {
                                                    sourceItem: Rectangle {
                                                        width: auraR8Art2.width
                                                        height: auraR8Art2.height
                                                        radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                                        color: "white"
                                                    }
                                                }
                                            }


                                            // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 START
                                            // Full-surface glass only: no pill-shaped highlight bars.
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                                z: 20
                                                opacity: 0.34
                                                gradient: Gradient {
                                                    GradientStop { position: 0.00; color: "#12FFFFFF" }
                                                    GradientStop { position: 0.30; color: "#035FDFFF" }
                                                    GradientStop { position: 0.68; color: "#00000000" }
                                                    GradientStop { position: 1.00; color: "#064A35FF" }
                                                }
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: Math.max(0, (Math.min(auraR8Art2.width, auraR8Art2.height) / 2) - 2)
                                                color: "transparent"
                                                border.width: 1
                                                border.color: "#E9FBFF"
                                                opacity: 0.15
                                                z: 21
                                            }
                                            // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 END


                                            // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 START
                                            // SAFE hover polish: opacity only. No scale/transform on layered Image.
                                            HoverHandler {
                                                id: auraR8Art2HoverSafe
                                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: Math.max(0, (Math.min(auraR8Art2.width, auraR8Art2.height) / 2) - 2)
                                                color: "transparent"
                                                border.width: 1
                                                border.color: "#79ECFF"
                                                opacity: auraR8Art2HoverSafe.hovered ? 0.42 : 0.0
                                                z: 44
                                                Behavior on opacity {
                                                    NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                                                }
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                                color: "#126D4CFF"
                                                opacity: auraR8Art2HoverSafe.hovered ? 0.12 : 0.0
                                                z: 43
                                                Behavior on opacity {
                                                    NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                                }
                                            }
                                            // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 END

                                            // AURA_NATIVE_MUSIC_PLAYING_STATE_R12 START
                                            // Playing-state ambience only. No scale, no click handler, no geometry change.
                                            property real auraR8Art2R12Pulse: 0.0
                                            SequentialAnimation on auraR8Art2R12Pulse {
                                                running: (musicBridge.playing)
                                                loops: Animation.Infinite
                                                NumberAnimation {
                                                    from: 0.04
                                                    to: 0.13
                                                    duration: 950
                                                    easing.type: Easing.InOutSine
                                                }
                                                NumberAnimation {
                                                    from: 0.13
                                                    to: 0.04
                                                    duration: 1050
                                                    easing.type: Easing.InOutSine
                                                }
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: Math.max(0, (Math.min(auraR8Art2.width, auraR8Art2.height) / 2) - 2)
                                                color: "transparent"
                                                border.width: 1
                                                border.color: "#71E8FF"
                                                opacity: (musicBridge.playing) ? (0.13 + auraR8Art2R12Pulse) : 0.0
                                                z: 48
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                                color: "#126B4CFF"
                                                opacity: (musicBridge.playing) ? (0.04 + (auraR8Art2R12Pulse * 0.35)) : 0.0
                                                z: 47
                                            }
                                            // AURA_NATIVE_MUSIC_PLAYING_STATE_R12 END
}
                                        // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 glass rings
                                        Rectangle {
                                            anchors.fill: auraR8Art2
                                            anchors.margins: -4
                                            radius: (Math.min(auraR8Art2.width, auraR8Art2.height) / 2) + 4
                                            color: "transparent"
                                            border.width: 1
                                            border.color: "#A06BFF"
                                            opacity: 0.34
                                            z: auraR8Art2.z + 1
                                        }
                                        Rectangle {
                                            anchors.fill: auraR8Art2
                                            radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                            color: "transparent"
                                            border.width: 1
                                            border.color: "#67E8FF"
                                            opacity: 0.72
                                            z: auraR8Art2.z + 3
                                        }
                                        Rectangle {
                                            anchors.fill: auraR8Art2
                                            radius: Math.min(auraR8Art2.width, auraR8Art2.height) / 2
                                            opacity: 0.72
                                            z: auraR8Art2.z + 2
                                            gradient: Gradient {
                                                GradientStop { position: 0.00; color: "#20FFFFFF" }
                                                GradientStop { position: 0.34; color: "#05FFFFFF" }
                                                GradientStop { position: 0.72; color: "#00000000" }
                                                GradientStop { position: 1.00; color: "#12030A18" }
                                            }
                                        }

                                    }

                                    Column {
                                        x: 58
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - 150
                                        spacing: 2

                                        Text {
                                            width: parent.width
                                            text: title
                                            color: root.textPrimary
                                            font.pixelSize: 9
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            width: parent.width
                                            text: artist.length ? artist : album
                                            color: root.textSecondary
                                            font.pixelSize: 7
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Text {
                                        anchors.right: playRecent.left
                                        anchors.rightMargin: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: favorite ? "♥" : ""
                                        color: root.purple
                                        font.pixelSize: 13
                                    }

                                    Rectangle {
                                        id: playRecent
                                        anchors.right: parent.right
                                        anchors.rightMargin: 7
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 68
                                        height: 30
                                        radius: 15
                                        color: "#3674EFFF"
                                        border.width: 1
                                        border.color: root.cyan

                                        Text {
                                            anchors.centerIn: parent
                                            text: "LIRE"
                                            color: "#ECFDFF"
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }

                                        TapHandler {
                                            onTapped: musicBridge.playId(itemId)
                                        }
                                    }

                                    HoverHandler {
                                        id: recentHover
                                    }

                                    TapHandler {
                                        onDoubleTapped: musicBridge.playId(itemId)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // =============================================================
            // PLAYER / NOW PLAYING
            // =============================================================
            Item {
                visible: root.page === "player"
                anchors.fill: parent

                Row {
                    anchors.centerIn: parent
                    width: Math.min(parent.width, 1120)
                    height: Math.min(parent.height, 650)
                    spacing: 42

                    Item {
                        width: 500
                        height: parent.height

                        Rectangle {
                            id: playerCover
                            width: Math.min(parent.width, parent.height - 80)
                            height: width
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 44
                            color: "#7A091520"
                            border.width: 1
                            border.color: musicBridge.playing ? root.cyan : "#4C6F83A0"
                            clip: true

                            Image {
                                id: auraR8Art3
                                anchors.fill: parent
                                anchors.margins: musicBridge.currentCover.length ? 0 : width * 0.30
                                source: musicBridge.currentCover.length
                                        ? musicBridge.currentCover
                                        : root.asset("music-note-premium.svg")
                                fillMode: musicBridge.currentCover.length
                                          ? Image.PreserveAspectCrop
                                          : Image.PreserveAspectFit
                                smooth: true
                                mipmap: true
                            
                                // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 real mask
                                layer.enabled: true
                                layer.effect: MultiEffect {
                                    maskEnabled: true
                                    maskSource: ShaderEffectSource {
                                        sourceItem: Rectangle {
                                            width: auraR8Art3.width
                                            height: auraR8Art3.height
                                            radius: 32
                                            color: "white"
                                        }
                                    }
                                }


                                // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 START
                                // Full-surface glass only: no pill-shaped highlight bars.
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 32
                                    z: 20
                                    opacity: 0.24
                                    gradient: Gradient {
                                        GradientStop { position: 0.00; color: "#0CFFFFFF" }
                                        GradientStop { position: 0.30; color: "#025FDFFF" }
                                        GradientStop { position: 0.68; color: "#00000000" }
                                        GradientStop { position: 1.00; color: "#044A35FF" }
                                    }
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    radius: Math.max(0, (32) - 2)
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#E9FBFF"
                                    opacity: 0.12
                                    z: 21
                                }
                                // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 END


                                // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 START
                                // SAFE hover polish: opacity only. No scale/transform on layered Image.
                                HoverHandler {
                                    id: auraR8Art3HoverSafe
                                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    radius: Math.max(0, (32) - 2)
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#79ECFF"
                                    opacity: auraR8Art3HoverSafe.hovered ? 0.28 : 0.0
                                    z: 44
                                    Behavior on opacity {
                                        NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                                    }
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 32
                                    color: "#126D4CFF"
                                    opacity: auraR8Art3HoverSafe.hovered ? 0.08 : 0.0
                                    z: 43
                                    Behavior on opacity {
                                        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                    }
                                }
                                // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 END

                                // AURA_NATIVE_MUSIC_PLAYING_STATE_R12 START
                                // Playing-state ambience only. No scale, no click handler, no geometry change.
                                property real auraR8Art3R12Pulse: 0.0
                                SequentialAnimation on auraR8Art3R12Pulse {
                                    running: (musicBridge.playing)
                                    loops: Animation.Infinite
                                    NumberAnimation {
                                        from: 0.02
                                        to: 0.075
                                        duration: 1100
                                        easing.type: Easing.InOutSine
                                    }
                                    NumberAnimation {
                                        from: 0.075
                                        to: 0.02
                                        duration: 1200
                                        easing.type: Easing.InOutSine
                                    }
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    radius: Math.max(0, (32) - 2)
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#71E8FF"
                                    opacity: (musicBridge.playing) ? (0.09 + auraR8Art3R12Pulse) : 0.0
                                    z: 48
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 32
                                    color: "#126B4CFF"
                                    opacity: (musicBridge.playing) ? (0.025 + (auraR8Art3R12Pulse * 0.35)) : 0.0
                                    z: 47
                                }
                                // AURA_NATIVE_MUSIC_PLAYING_STATE_R12 END
}
                            // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 glass rings
                            Rectangle {
                                anchors.fill: auraR8Art3
                                anchors.margins: -4
                                radius: (32) + 4
                                color: "transparent"
                                border.width: 1
                                border.color: "#A06BFF"
                                opacity: 0.22
                                z: auraR8Art3.z + 1
                            }
                            Rectangle {
                                anchors.fill: auraR8Art3
                                radius: 32
                                color: "transparent"
                                border.width: 1
                                border.color: "#67E8FF"
                                opacity: 0.48
                                z: auraR8Art3.z + 3
                            }
                            Rectangle {
                                anchors.fill: auraR8Art3
                                radius: 32
                                opacity: 0.42
                                z: auraR8Art3.z + 2
                                gradient: Gradient {
                                    GradientStop { position: 0.00; color: "#20FFFFFF" }
                                    GradientStop { position: 0.34; color: "#05FFFFFF" }
                                    GradientStop { position: 0.72; color: "#00000000" }
                                    GradientStop { position: 1.00; color: "#12030A18" }
                                }
                            }


                            Rectangle {
                                anchors.fill: parent
                                radius: 44
                                color: "transparent"
                                border.width: 1
                                border.color: "#28FFFFFF"
                            }
                        }
                    }

                    Column {
                        width: parent.width - 542
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 15

                        Text {
                            text: "NOW PLAYING"
                            color: root.cyan
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.7
                        }

                        Text {
                            width: parent.width
                            text: musicBridge.currentTitle.length
                                  ? musicBridge.currentTitle
                                  : "Aucun média en lecture"
                            color: root.textPrimary
                            font.pixelSize: 30
                            font.weight: Font.DemiBold
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            width: parent.width
                            text: [
                                musicBridge.currentArtist,
                                musicBridge.currentAlbum
                            ].filter(function(x) {
                                return String(x || "").length
                            }).join(" · ")
                            color: root.textSecondary
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Row {
                            spacing: 8

                            Rectangle {
                                width: 84
                                height: 28
                                radius: 14
                                color: root.surfaceSoft
                                border.width: 1
                                border.color: root.stroke

                                Text {
                                    anchors.centerIn: parent
                                    text: musicBridge.currentExtension.length
                                          ? musicBridge.currentExtension.toUpperCase()
                                          : "LOCAL"
                                    color: "#9CE8F4"
                                    font.pixelSize: 7
                                }
                            }

                            Rectangle {
                                width: 88
                                height: 28
                                radius: 14
                                color: root.surfaceSoft
                                border.width: 1
                                border.color: root.stroke

                                Text {
                                    anchors.centerIn: parent
                                    text: musicBridge.currentYear.length
                                          ? musicBridge.currentYear
                                          : "BIBLIOTHÈQUE"
                                    color: "#BDA9F5"
                                    font.pixelSize: 7
                                }
                            }

                            Rectangle {
                                width: 42
                                height: 42
                                radius: 21
                                color: musicBridge.currentFavorite
                                       ? "#379A72FF"
                                       : root.surfaceSoft
                                border.width: 1
                                border.color: musicBridge.currentFavorite
                                              ? root.purple
                                              : root.stroke

                                Image {
                                    anchors.centerIn: parent
                                    width: 19
                                    height: 19
                                    source: root.asset("music-heart-premium.svg")
                                    opacity: musicBridge.currentFavorite ? 1.0 : 0.58
                                }

                                TapHandler {
                                    onTapped: musicBridge.setFavorite(
                                        musicBridge.currentId,
                                        !musicBridge.currentFavorite
                                    )
                                }
                            }
                        }

                        Slider {
                            id: seekSlider
                            width: parent.width
                            from: 0
                            to: 100
                            value: musicBridge.progress * 100
                            onPressedChanged: {
                                if (!pressed)
                                    musicBridge.seekPercent(value)
                            }

                            background: Rectangle {
                                x: seekSlider.leftPadding
                                y: seekSlider.topPadding + seekSlider.availableHeight / 2 - height / 2
                                width: seekSlider.availableWidth
                                height: 5
                                radius: 3
                                color: "#35304859"

                                Rectangle {
                                    width: seekSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: 3
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: root.cyan }
                                        GradientStop { position: 1.0; color: root.purple }
                                    }
                                }
                            }

                            handle: Rectangle {
                                x: seekSlider.leftPadding
                                   + seekSlider.visualPosition
                                   * (seekSlider.availableWidth - width)
                                y: seekSlider.topPadding
                                   + seekSlider.availableHeight / 2
                                   - height / 2
                                width: 16
                                height: 16
                                radius: 8
                                color: "#E1FCFF"
                                border.width: 1
                                border.color: root.cyan
                            }
                        }

                        Row {
                            width: parent.width

                            Text {
                                width: parent.width / 2
                                text: musicBridge.positionLabel
                                color: root.textSecondary
                                font.pixelSize: 7
                            }

                            Text {
                                width: parent.width / 2
                                text: musicBridge.durationLabel
                                horizontalAlignment: Text.AlignRight
                                color: root.textSecondary
                                font.pixelSize: 7
                            }
                        }

                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 15

                            Repeater {
                                model: [
                                    { key: "prev", icon: "music-prev-premium.svg" },
                                    { key: "play", icon: musicBridge.playing ? "music-pause-premium.svg" : "music-play-premium.svg" },
                                    { key: "next", icon: "music-next-premium.svg" },
                                    { key: "stop", icon: "music-stop-premium.svg" }
                                ]

                                Rectangle {
                                    required property var modelData

                                    width: modelData.key === "play" ? 72 : 52
                                    height: width
                                    radius: width / 2
                                    color: playerButtonHover.hovered
                                           ? "#82101F34"
                                           : root.surface
                                    border.width: 1
                                    border.color: modelData.key === "play"
                                                  ? "#6574EFFF"
                                                  : modelData.key === "stop"
                                                    ? "#5AFF789A"
                                                    : "#3E6B86A0"

                                    Image {
                                        anchors.centerIn: parent
                                        width: parent.width * 0.42
                                        height: width
                                        source: root.asset(modelData.icon)
                                        fillMode: Image.PreserveAspectFit
                                    }

                                    HoverHandler {
                                        id: playerButtonHover
                                    }

                                    TapHandler {
                                        onTapped: {
                                            if (modelData.key === "prev")
                                                musicBridge.previous()
                                            else if (modelData.key === "play")
                                                musicBridge.togglePlay()
                                            else if (modelData.key === "next")
                                                musicBridge.next()
                                            else
                                                musicBridge.stop()
                                        }
                                    }
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 10

                            Rectangle {
                                width: (parent.width - 10) / 2
                                height: 38
                                radius: 19
                                color: musicBridge.shuffle
                                       ? "#2F74EFFF"
                                       : root.surfaceSoft
                                border.width: 1
                                border.color: musicBridge.shuffle
                                              ? root.cyan
                                              : root.stroke

                                Text {
                                    anchors.centerIn: parent
                                    text: musicBridge.shuffle
                                          ? "ALÉATOIRE · ON"
                                          : "ALÉATOIRE · OFF"
                                    color: musicBridge.shuffle
                                           ? "#D7FBFF"
                                           : root.textSecondary
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }

                                TapHandler {
                                    onTapped: musicBridge.toggleShuffle()
                                }
                            }

                            Rectangle {
                                width: (parent.width - 10) / 2
                                height: 38
                                radius: 19
                                color: musicBridge.repeatMode !== "off"
                                       ? "#2E9A72FF"
                                       : root.surfaceSoft
                                border.width: 1
                                border.color: musicBridge.repeatMode !== "off"
                                              ? root.purple
                                              : root.stroke

                                Text {
                                    anchors.centerIn: parent
                                    text: musicBridge.repeatMode === "one"
                                          ? "RÉPÉTER · 1"
                                          : musicBridge.repeatMode === "all"
                                            ? "RÉPÉTER · TOUT"
                                            : "RÉPÉTER · OFF"
                                    color: musicBridge.repeatMode !== "off"
                                           ? "#E4DAFF"
                                           : root.textSecondary
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }

                                TapHandler {
                                    onTapped: musicBridge.cycleRepeat()
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 10

                            Text {
                                width: 56
                                anchors.verticalCenter: parent.verticalCenter
                                text: "VOLUME"
                                color: root.textSecondary
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }

                            Slider {
                                width: parent.width - 108
                                from: 0
                                to: 100
                                value: musicBridge.volume
                                onMoved: musicBridge.setVolume(Math.round(value))
                            }

                            Text {
                                width: 32
                                anchors.verticalCenter: parent.verticalCenter
                                text: musicBridge.volume + "%"
                                horizontalAlignment: Text.AlignRight
                                color: "#B9EFF6"
                                font.pixelSize: 8
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: 54
                            radius: 18
                            color: root.surfaceSoft
                            border.width: 1
                            border.color: root.stroke

                            Row {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 18

                                Column {
                                    width: parent.width / 2 - 9

                                    Text {
                                        text: "WINDOWS MEDIA KEYS"
                                        color: root.textSecondary
                                        font.pixelSize: 7
                                    }

                                    Text {
                                        text: musicBridge.hotkeysLabel
                                        color: "#B8EAF3"
                                        font.pixelSize: 8
                                    }
                                }

                                Column {
                                    width: parent.width / 2 - 9

                                    Text {
                                        text: "SMTC"
                                        color: root.textSecondary
                                        font.pixelSize: 7
                                    }

                                    Text {
                                        text: musicBridge.smtcLabel
                                        color: "#B8EAF3"
                                        font.pixelSize: 8
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // =============================================================
            // LIBRARY
            // =============================================================
            Item {
                visible: root.page === "library"
                anchors.fill: parent

                Column {
                    anchors.fill: parent
                    spacing: 14

                    Row {
                        width: parent.width

                        Column {
                            width: parent.width - 390
                            spacing: 4

                            Text {
                                text: "BIBLIOTHÈQUE"
                                color: root.textPrimary
                                font.pixelSize: 34
                                font.weight: Font.DemiBold
                                font.letterSpacing: -0.5
                            }

                            Text {
                                text: "Vos titres locaux · recherche · favoris · doublons"
                                color: root.textSecondary
                                font.pixelSize: 8
                            }
                        }

                        Row {
                            width: 390
                            spacing: 8

                            Repeater {
                                model: [
                                    { label: "TITRES", act: "track" },
                                    { label: "DOSSIER", act: "folder" },
                                    { label: "MÉTADONNÉES", act: "meta" }
                                ]

                                Rectangle {
                                    required property var modelData
                                    width: modelData.act === "meta" ? 122 : 110
                                    height: 34
                                    radius: 17
                                    color: libraryActionHover.hovered
                                           ? "#2C74EFFF"
                                           : root.surfaceSoft
                                    border.width: 1
                                    border.color: "#3B74EFFF"

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: "#C6F7FD"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    HoverHandler {
                                        id: libraryActionHover
                                    }

                                    TapHandler {
                                        onTapped: {
                                            if (modelData.act === "track")
                                                musicBridge.pickTrack()
                                            else if (modelData.act === "folder")
                                                musicBridge.pickFolder()
                                            else
                                                musicBridge.refreshMetadata()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 10

                        Rectangle {
                            width: parent.width - 392
                            height: 42
                            radius: 21
                            color: root.surfaceSoft
                            border.width: 1
                            border.color: root.stroke

                            Image {
                                x: 15
                                anchors.verticalCenter: parent.verticalCenter
                                width: 17
                                height: 17
                                source: root.asset("music-search-premium.svg")
                                fillMode: Image.PreserveAspectFit
                            }

                            TextField {
                                x: 44
                                width: parent.width - 58
                                anchors.verticalCenter: parent.verticalCenter
                                placeholderText: "Rechercher dans la bibliothèque..."
                                text: root.libraryQuery
                                color: root.textPrimary
                                placeholderTextColor: root.textSecondary
                                font.pixelSize: 9
                                background: Rectangle {
                                    color: "transparent"
                                }

                                onTextChanged: {
                                    root.libraryQuery = text
                                    root.applyLibraryFilter()
                                }
                            }
                        }

                        Rectangle {
                            width: 112
                            height: 42
                            radius: 21
                            color: root.favoritesOnly
                                   ? "#329A72FF"
                                   : root.surfaceSoft
                            border.width: 1
                            border.color: root.favoritesOnly
                                          ? root.purple
                                          : root.stroke

                            Text {
                                anchors.centerIn: parent
                                text: root.favoritesOnly ? "♥ FAVORIS" : "♡ FAVORIS"
                                color: root.favoritesOnly
                                       ? "#E4D8FF"
                                       : root.textSecondary
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }

                            TapHandler {
                                onTapped: {
                                    root.favoritesOnly = !root.favoritesOnly
                                    root.applyLibraryFilter()
                                }
                            }
                        }

                        Rectangle {
                            width: 112
                            height: 42
                            radius: 21
                            color: root.duplicatesOnly
                                   ? "#2E74EFFF"
                                   : root.surfaceSoft
                            border.width: 1
                            border.color: root.duplicatesOnly
                                          ? root.cyan
                                          : root.stroke

                            Text {
                                anchors.centerIn: parent
                                text: "DOUBLONS"
                                color: root.duplicatesOnly
                                       ? "#D4FBFF"
                                       : root.textSecondary
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }

                            TapHandler {
                                onTapped: {
                                    root.duplicatesOnly = !root.duplicatesOnly
                                    root.applyLibraryFilter()
                                }
                            }
                        }

                        ComboBox {
                            id: sortBox
                            width: 128
                            height: 42
                            model: ["PLAYLIST", "TITRE", "ARTISTE", "ALBUM", "AJOUT"]
                            currentIndex: root.librarySort === "title"
                                          ? 1
                                          : root.librarySort === "artist"
                                            ? 2
                                            : root.librarySort === "album"
                                              ? 3
                                              : root.librarySort === "recent"
                                                ? 4
                                                : 0

                            onActivated: {
                                root.librarySort = currentIndex === 1
                                                   ? "title"
                                                   : currentIndex === 2
                                                     ? "artist"
                                                     : currentIndex === 3
                                                       ? "album"
                                                       : currentIndex === 4
                                                         ? "recent"
                                                         : "playlist"
                                root.applyLibraryFilter()
                            }
                        }
                    }

                    ListView {
                        id: libraryList
                        width: parent.width
                        height: parent.height - y
                        clip: true
                        spacing: 7
                        model: musicLibraryModel

                        delegate: Rectangle {
                            required property int index
                            required property string itemId
                            required property string title
                            required property string artist
                            required property string album
                            required property string durationLabel
                            required property string extension
                            required property string year
                            required property string coverDataUri
                            required property bool favorite

                            width: libraryList.width
                            height: 62
                            radius: 20
                            color: libraryHover.hovered
                                   ? "#5F0C1A28"
                                   : index % 2 === 0
                                     ? "#2207111C"
                                     : "transparent"
                            border.width: musicBridge.currentId === itemId ? 1 : 0
                            border.color: root.cyan

                            Rectangle {
                                x: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 48
                                height: 48
                                radius: 14
                                color: "#6C0A1521"
                                clip: true

                                Image {
                                    id: auraR8Art4
                                    anchors.fill: parent
                                    anchors.margins: coverDataUri.length ? 0 : 12
                                    source: coverDataUri.length
                                            ? coverDataUri
                                            : root.asset("music-note-premium.svg")
                                    fillMode: coverDataUri.length
                                              ? Image.PreserveAspectCrop
                                              : Image.PreserveAspectFit
                                
                                    // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 real mask
                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        maskEnabled: true
                                        maskSource: ShaderEffectSource {
                                            sourceItem: Rectangle {
                                                width: auraR8Art4.width
                                                height: auraR8Art4.height
                                                radius: 16
                                                color: "white"
                                            }
                                        }
                                    }


                                    // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 START
                                    // Full-surface glass only: no pill-shaped highlight bars.
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 16
                                        z: 20
                                        opacity: 0.18
                                        gradient: Gradient {
                                            GradientStop { position: 0.00; color: "#08FFFFFF" }
                                            GradientStop { position: 0.30; color: "#015FDFFF" }
                                            GradientStop { position: 0.68; color: "#00000000" }
                                            GradientStop { position: 1.00; color: "#034A35FF" }
                                        }
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        radius: Math.max(0, (16) - 1)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: "#E9FBFF"
                                        opacity: 0.09
                                        z: 21
                                    }
                                    // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 END


                                    // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 START
                                    // SAFE hover polish: opacity only. No scale/transform on layered Image.
                                    HoverHandler {
                                        id: auraR8Art4HoverSafe
                                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        radius: Math.max(0, (16) - 1)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: "#79ECFF"
                                        opacity: auraR8Art4HoverSafe.hovered ? 0.22 : 0.0
                                        z: 44
                                        Behavior on opacity {
                                            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                                        }
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 16
                                        color: "#126D4CFF"
                                        opacity: auraR8Art4HoverSafe.hovered ? 0.06 : 0.0
                                        z: 43
                                        Behavior on opacity {
                                            NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                        }
                                    }
                                    // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 END
}
                                // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 glass rings
                                Rectangle {
                                    anchors.fill: auraR8Art4
                                    anchors.margins: -4
                                    radius: (16) + 4
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#A06BFF"
                                    opacity: 0.16
                                    z: auraR8Art4.z + 1
                                }
                                Rectangle {
                                    anchors.fill: auraR8Art4
                                    radius: 16
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#67E8FF"
                                    opacity: 0.42
                                    z: auraR8Art4.z + 3
                                }
                                Rectangle {
                                    anchors.fill: auraR8Art4
                                    radius: 16
                                    opacity: 0.34
                                    z: auraR8Art4.z + 2
                                    gradient: Gradient {
                                        GradientStop { position: 0.00; color: "#20FFFFFF" }
                                        GradientStop { position: 0.34; color: "#05FFFFFF" }
                                        GradientStop { position: 0.72; color: "#00000000" }
                                        GradientStop { position: 1.00; color: "#12030A18" }
                                    }
                                }

                            }

                            Column {
                                x: 70
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 410
                                spacing: 3

                                Text {
                                    width: parent.width
                                    text: title
                                    color: root.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: [
                                        artist,
                                        album,
                                        year
                                    ].filter(function(x) {
                                        return String(x || "").length
                                    }).join(" · ")
                                    color: root.textSecondary
                                    font.pixelSize: 7
                                    elide: Text.ElideRight
                                }
                            }

                            Row {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 7

                                Text {
                                    width: 48
                                    text: durationLabel
                                    color: root.textSecondary
                                    font.pixelSize: 7
                                    horizontalAlignment: Text.AlignRight
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Rectangle {
                                    width: 50
                                    height: 28
                                    radius: 14
                                    color: root.surfaceSoft
                                    border.width: 1
                                    border.color: root.stroke

                                    Text {
                                        anchors.centerIn: parent
                                        text: extension.toUpperCase()
                                        color: "#8EDDEA"
                                        font.pixelSize: 7
                                    }
                                }

                                Rectangle {
                                    width: 40
                                    height: 40
                                    radius: 20
                                    color: favorite ? "#329A72FF" : root.surfaceSoft
                                    border.width: 1
                                    border.color: favorite ? root.purple : root.stroke

                                    Image {
                                        anchors.centerIn: parent
                                        width: 18
                                        height: 18
                                        source: root.asset("music-heart-premium.svg")
                                        opacity: favorite ? 1.0 : 0.48
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.setFavorite(itemId, !favorite)
                                    }
                                }

                                Rectangle {
                                    width: 78
                                    height: 34
                                    radius: 17
                                    color: "#3474EFFF"
                                    border.width: 1
                                    border.color: root.cyan

                                    Text {
                                        anchors.centerIn: parent
                                        text: "ENSUITE"
                                        color: "#DFFBFF"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.playNext(itemId)
                                    }
                                }

                                Rectangle {
                                    width: 72
                                    height: 34
                                    radius: 17
                                    color: "#4174EFFF"
                                    border.width: 1
                                    border.color: root.cyan

                                    Text {
                                        anchors.centerIn: parent
                                        text: "LIRE"
                                        color: "#F0FDFF"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.playId(itemId)
                                    }
                                }
                            }

                            HoverHandler {
                                id: libraryHover
                            }

                            TapHandler {
                                onDoubleTapped: musicBridge.playId(itemId)
                            }
                        }
                    }
                }
            }

            // =============================================================
            // QUEUE
            // =============================================================
            Item {
                visible: root.page === "queue"
                anchors.fill: parent

                Column {
                    anchors.fill: parent
                    spacing: 14

                    Row {
                        width: parent.width

                        Column {
                            width: parent.width - 560
                            spacing: 4

                            Text {
                                text: "À SUIVRE"
                                color: root.textPrimary
                                font.pixelSize: 34
                                font.weight: Font.DemiBold
                            }

                            Text {
                                text: "Réorganisez la file comme dans Chromium"
                                color: root.textSecondary
                                font.pixelSize: 8
                            }
                        }

                        Row {
                            width: 560
                            spacing: 8

                            Repeater {
                                model: [
                                    { label: "+ TITRES", action: "track" },
                                    { label: "+ DOSSIER", action: "folder" },
                                    { label: "IMPORT M3U", action: "import" },
                                    { label: "EXPORT M3U", action: "export" },
                                    { label: "VIDER", action: "clear" }
                                ]

                                Rectangle {
                                    required property var modelData
                                    width: 104
                                    height: 34
                                    radius: 17
                                    color: queueActionHover.hovered ? "#2D74EFFF" : root.surfaceSoft
                                    border.width: 1
                                    border.color: modelData.action === "clear"
                                                  ? "#4CFF789A"
                                                  : "#3C74EFFF"

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: modelData.action === "clear"
                                               ? "#FF9AAE"
                                               : "#C7F7FD"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    HoverHandler {
                                        id: queueActionHover
                                    }

                                    TapHandler {
                                        onTapped: {
                                            if (modelData.action === "track")
                                                musicBridge.pickTrack()
                                            else if (modelData.action === "folder")
                                                musicBridge.pickFolder()
                                            else if (modelData.action === "import")
                                                musicBridge.importM3U()
                                            else if (modelData.action === "export")
                                                musicBridge.exportM3U()
                                            else
                                                musicBridge.clearPlaylist()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ListView {
                        id: queueList
                        width: parent.width
                        height: parent.height - y
                        clip: true
                        spacing: 7
                        model: musicPlaylistModel

                        delegate: Rectangle {
                            required property int index
                            required property string itemId
                            required property string title
                            required property string artist
                            required property string album
                            required property string durationLabel
                            required property string coverDataUri

                            width: queueList.width
                            height: 64
                            radius: 20
                            color: musicBridge.currentId === itemId
                                   ? "#4B173448"
                                   : queueHover.hovered
                                     ? "#570C1A28"
                                     : "transparent"
                            border.width: musicBridge.currentId === itemId ? 1 : 0
                            border.color: root.cyan

                            Text {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: 34
                                text: String(index + 1).padStart(2, "0")
                                color: musicBridge.currentId === itemId
                                       ? root.cyan
                                       : root.textSecondary
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }

                            Rectangle {
                                x: 48
                                anchors.verticalCenter: parent.verticalCenter
                                width: 48
                                height: 48
                                radius: 14
                                color: "#6B0A1521"
                                clip: true

                                Image {
                                    id: auraR8Art5
                                    anchors.fill: parent
                                    anchors.margins: coverDataUri.length ? 0 : 12
                                    source: coverDataUri.length
                                            ? coverDataUri
                                            : root.asset("music-note-premium.svg")
                                    fillMode: coverDataUri.length
                                              ? Image.PreserveAspectCrop
                                              : Image.PreserveAspectFit
                                
                                    // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 real mask
                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        maskEnabled: true
                                        maskSource: ShaderEffectSource {
                                            sourceItem: Rectangle {
                                                width: auraR8Art5.width
                                                height: auraR8Art5.height
                                                radius: 16
                                                color: "white"
                                            }
                                        }
                                    }


                                    // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 START
                                    // Full-surface glass only: no pill-shaped highlight bars.
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 16
                                        z: 20
                                        opacity: 0.18
                                        gradient: Gradient {
                                            GradientStop { position: 0.00; color: "#08FFFFFF" }
                                            GradientStop { position: 0.30; color: "#015FDFFF" }
                                            GradientStop { position: 0.68; color: "#00000000" }
                                            GradientStop { position: 1.00; color: "#034A35FF" }
                                        }
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        radius: Math.max(0, (16) - 1)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: "#E9FBFF"
                                        opacity: 0.09
                                        z: 21
                                    }
                                    // AURA_NATIVE_MUSIC_PREMIUM_GLASS_R10_FIX2 END


                                    // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 START
                                    // SAFE hover polish: opacity only. No scale/transform on layered Image.
                                    HoverHandler {
                                        id: auraR8Art5HoverSafe
                                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        radius: Math.max(0, (16) - 1)
                                        color: "transparent"
                                        border.width: 1
                                        border.color: "#79ECFF"
                                        opacity: auraR8Art5HoverSafe.hovered ? 0.22 : 0.0
                                        z: 44
                                        Behavior on opacity {
                                            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                                        }
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 16
                                        color: "#126D4CFF"
                                        opacity: auraR8Art5HoverSafe.hovered ? 0.06 : 0.0
                                        z: 43
                                        Behavior on opacity {
                                            NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                        }
                                    }
                                    // AURA_NATIVE_MUSIC_INTERACTIONS_R11_FIX1 END
}
                                // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 glass rings
                                Rectangle {
                                    anchors.fill: auraR8Art5
                                    anchors.margins: -4
                                    radius: (16) + 4
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#A06BFF"
                                    opacity: 0.16
                                    z: auraR8Art5.z + 1
                                }
                                Rectangle {
                                    anchors.fill: auraR8Art5
                                    radius: 16
                                    color: "transparent"
                                    border.width: 1
                                    border.color: "#67E8FF"
                                    opacity: 0.42
                                    z: auraR8Art5.z + 3
                                }
                                Rectangle {
                                    anchors.fill: auraR8Art5
                                    radius: 16
                                    opacity: 0.34
                                    z: auraR8Art5.z + 2
                                    gradient: Gradient {
                                        GradientStop { position: 0.00; color: "#20FFFFFF" }
                                        GradientStop { position: 0.34; color: "#05FFFFFF" }
                                        GradientStop { position: 0.72; color: "#00000000" }
                                        GradientStop { position: 1.00; color: "#12030A18" }
                                    }
                                }

                            }

                            Column {
                                x: 112
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 430
                                spacing: 3

                                Text {
                                    width: parent.width
                                    text: title
                                    color: root.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    text: [artist, album].filter(function(x) {
                                        return String(x || "").length
                                    }).join(" · ")
                                    color: root.textSecondary
                                    font.pixelSize: 7
                                    elide: Text.ElideRight
                                }
                            }

                            Row {
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 7

                                Text {
                                    width: 50
                                    text: durationLabel
                                    horizontalAlignment: Text.AlignRight
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: root.textSecondary
                                    font.pixelSize: 7
                                }

                                Repeater {
                                    model: [
                                        { label: "↑", d: -1 },
                                        { label: "↓", d: 1 }
                                    ]

                                    Rectangle {
                                        required property var modelData
                                        width: 34
                                        height: 34
                                        radius: 17
                                        color: root.surfaceSoft
                                        border.width: 1
                                        border.color: root.stroke

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: "#A9EAF4"
                                            font.pixelSize: 12
                                        }

                                        TapHandler {
                                            onTapped: musicBridge.moveItem(itemId, modelData.d)
                                        }
                                    }
                                }

                                Rectangle {
                                    width: 82
                                    height: 34
                                    radius: 17
                                    color: root.surfaceSoft
                                    border.width: 1
                                    border.color: root.stroke

                                    Text {
                                        anchors.centerIn: parent
                                        text: "ENSUITE"
                                        color: "#A9EAF4"
                                        font.pixelSize: 7
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.playNext(itemId)
                                    }
                                }

                                Rectangle {
                                    width: 66
                                    height: 34
                                    radius: 17
                                    color: "#4374EFFF"
                                    border.width: 1
                                    border.color: root.cyan

                                    Text {
                                        anchors.centerIn: parent
                                        text: "LIRE"
                                        color: "#F0FDFF"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.playId(itemId)
                                    }
                                }

                                Rectangle {
                                    width: 34
                                    height: 34
                                    radius: 17
                                    color: "#32161120"
                                    border.width: 1
                                    border.color: "#4CFF789A"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "×"
                                        color: "#FF93A9"
                                        font.pixelSize: 14
                                    }

                                    TapHandler {
                                        onTapped: musicBridge.removeItem(itemId)
                                    }
                                }
                            }

                            HoverHandler {
                                id: queueHover
                            }
                        }
                    }
                }
            }

            // =============================================================
            // PLAYLISTS
            // =============================================================
            Item {
                visible: root.page === "playlists"
                anchors.fill: parent

                Column {
                    anchors.fill: parent
                    spacing: 16

                    Text {
                        text: "PLAYLISTS"
                        color: root.textPrimary
                        font.pixelSize: 34
                        font.weight: Font.DemiBold
                    }

                    Row {
                        width: parent.width
                        spacing: 10

                        Rectangle {
                            width: parent.width - 160
                            height: 44
                            radius: 22
                            color: root.surfaceSoft
                            border.width: 1
                            border.color: root.stroke

                            TextField {
                                id: playlistName
                                anchors.fill: parent
                                anchors.leftMargin: 15
                                anchors.rightMargin: 15
                                placeholderText: "Nom de la nouvelle playlist..."
                                placeholderTextColor: root.textSecondary
                                color: root.textPrimary
                                font.pixelSize: 9
                                background: Rectangle {
                                    color: "transparent"
                                }
                            }
                        }

                        Rectangle {
                            width: 150
                            height: 44
                            radius: 22
                            color: "#3674EFFF"
                            border.width: 1
                            border.color: root.cyan

                            Text {
                                anchors.centerIn: parent
                                text: "ENREGISTRER LA FILE"
                                color: "#EDFDFF"
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }

                            TapHandler {
                                onTapped: {
                                    musicBridge.saveCollection(playlistName.text)
                                    playlistName.text = ""
                                }
                            }
                        }
                    }

                    Flickable {
                        width: parent.width
                        height: parent.height - y
                        contentWidth: width
                        contentHeight: collectionsColumn.height
                        clip: true

                        Column {
                            id: collectionsColumn
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: musicBridge.collections

                                Rectangle {
                                    property var row: modelData
                                    property string collectionId: String(
                                        row.id || row.collection_id || ""
                                    )
                                    property string collectionName: String(
                                        row.name || row.title || "Playlist"
                                    )
                                    property int collectionCount: Number(
                                        row.count || row.items_count || 0
                                    )

                                    width: collectionsColumn.width
                                    height: 74
                                    radius: 22
                                    color: collectionHover.hovered
                                           ? "#570C1A28"
                                           : root.surfaceSoft
                                    border.width: 1
                                    border.color: root.selectedCollectionId === collectionId
                                                  ? root.purple
                                                  : root.stroke

                                    Rectangle {
                                        x: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 50
                                        height: 50
                                        radius: 16
                                        color: "#650A1521"
                                        border.width: 1
                                        border.color: "#4B8A69E1"

                                        Image {
                                            anchors.centerIn: parent
                                            width: 24
                                            height: 24
                                            source: root.asset("music-nav-playlists.svg")
                                            fillMode: Image.PreserveAspectFit
                                        }
                                    }

                                    Column {
                                        x: 78
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - 360
                                        spacing: 4

                                        Text {
                                            width: parent.width
                                            text: collectionName
                                            color: root.textPrimary
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: collectionCount + " titres"
                                            color: root.textSecondary
                                            font.pixelSize: 7
                                        }
                                    }

                                    Row {
                                        anchors.right: parent.right
                                        anchors.rightMargin: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 8

                                        Rectangle {
                                            width: 86
                                            height: 34
                                            radius: 17
                                            color: "#3974EFFF"
                                            border.width: 1
                                            border.color: root.cyan

                                            Text {
                                                anchors.centerIn: parent
                                                text: "CHARGER"
                                                color: "#EAFDFF"
                                                font.pixelSize: 7
                                                font.weight: Font.DemiBold
                                            }

                                            TapHandler {
                                                onTapped: {
                                                    root.selectedCollectionId = collectionId
                                                    musicBridge.loadCollection(collectionId)
                                                }
                                            }
                                        }

                                        Rectangle {
                                            width: 86
                                            height: 34
                                            radius: 17
                                            color: "#32161120"
                                            border.width: 1
                                            border.color: "#4FFF789A"

                                            Text {
                                                anchors.centerIn: parent
                                                text: "SUPPRIMER"
                                                color: "#FF9AAE"
                                                font.pixelSize: 7
                                            }

                                            TapHandler {
                                                onTapped: musicBridge.deleteCollection(collectionId)
                                            }
                                        }
                                    }

                                    HoverHandler {
                                        id: collectionHover
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // =============================================================
            // HISTORY
            // =============================================================
            Item {
                visible: root.page === "history"
                anchors.fill: parent

                Column {
                    anchors.fill: parent
                    spacing: 14

                    Row {
                        width: parent.width

                        Column {
                            width: parent.width - 150

                            Text {
                                text: "HISTORIQUE"
                                color: root.textPrimary
                                font.pixelSize: 34
                                font.weight: Font.DemiBold
                            }

                            Text {
                                text: "Vos dernières écoutes locales"
                                color: root.textSecondary
                                font.pixelSize: 8
                            }
                        }

                        Rectangle {
                            width: 140
                            height: 36
                            radius: 18
                            anchors.verticalCenter: parent.verticalCenter
                            color: "#32161120"
                            border.width: 1
                            border.color: "#4EFF789A"

                            Text {
                                anchors.centerIn: parent
                                text: "EFFACER L'HISTORIQUE"
                                color: "#FF9AAE"
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }

                            TapHandler {
                                onTapped: musicBridge.clearHistory()
                            }
                        }
                    }

                    Flickable {
                        width: parent.width
                        height: parent.height - y
                        contentWidth: width
                        contentHeight: historyColumn.height
                        clip: true

                        Column {
                            id: historyColumn
                            width: parent.width
                            spacing: 7

                            Repeater {
                                model: musicBridge.history

                                Rectangle {
                                    property var row: modelData
                                    property string historyId: String(
                                        row.id || row.item_id || ""
                                    )
                                    property string historyTitle: String(
                                        row.title || "Titre"
                                    )
                                    property string historyArtist: String(
                                        row.artist || row.album || ""
                                    )
                                    property string historyCover: String(
                                        row.cover_data_uri || row.coverDataUri || ""
                                    )

                                    width: historyColumn.width
                                    height: 58
                                    radius: 20
                                    color: historyHover.hovered
                                           ? "#570C1A28"
                                           : "transparent"

                                    Rectangle {
                                        x: 7
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 44
                                        height: 44
                                        radius: 13
                                        color: "#6A0A1521"
                                        clip: true

                                        Image {
                                            anchors.fill: parent
                                            anchors.margins: historyCover.length ? 0 : 11
                                            source: historyCover.length
                                                    ? historyCover
                                                    : root.asset("music-note-premium.svg")
                                            fillMode: historyCover.length
                                                      ? Image.PreserveAspectCrop
                                                      : Image.PreserveAspectFit
                                        }
                                    }

                                    Column {
                                        x: 64
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width - 160
                                        spacing: 3

                                        Text {
                                            width: parent.width
                                            text: historyTitle
                                            color: root.textPrimary
                                            font.pixelSize: 9
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            width: parent.width
                                            text: historyArtist
                                            color: root.textSecondary
                                            font.pixelSize: 7
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Rectangle {
                                        anchors.right: parent.right
                                        anchors.rightMargin: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 72
                                        height: 32
                                        radius: 16
                                        color: "#3674EFFF"
                                        border.width: 1
                                        border.color: root.cyan

                                        Text {
                                            anchors.centerIn: parent
                                            text: "LIRE"
                                            color: "#EEFDFF"
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }

                                        TapHandler {
                                            onTapped: {
                                                if (historyId.length)
                                                    musicBridge.playId(historyId)
                                            }
                                        }
                                    }

                                    HoverHandler {
                                        id: historyHover
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // -----------------------------------------------------------------
        // Floating navigation like PixelPlayer, adapted for desktop.
        // -----------------------------------------------------------------
        Rectangle {
            id: bottomNav
            width: 690
            height: 64
            radius: 32
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 16
            color: root.lightMode ? "#D9FFFFFF" : "#D10A121D"
            border.width: 1
            border.color: root.lightMode ? "#3A65839A" : "#3B6A85A0"

            Row {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 4

                Repeater {
                    model: ["home", "player", "library", "queue", "playlists", "history"]

                    Rectangle {
                        required property string modelData

                        width: (parent.width - 20) / 6
                        height: parent.height
                        radius: 26
                        color: root.page === modelData
                               ? (root.lightMode ? "#C7EAF8FF" : "#5B173348")
                               : navHover.hovered
                                 ? (root.lightMode ? "#CFFFFFFF" : "#350D1824")
                                 : "transparent"

                        Column {
                            anchors.centerIn: parent
                            spacing: 3

                            Image {
                                width: 20
                                height: 20
                                anchors.horizontalCenter: parent.horizontalCenter
                                source: root.navIcon(modelData)
                                fillMode: Image.PreserveAspectFit
                                opacity: root.page === modelData ? 1.0 : 0.68
                            }

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: root.navLabel(modelData)
                                color: root.page === modelData
                                       ? "#DDFBFF"
                                       : root.textSecondary
                                font.pixelSize: 7
                                font.weight: root.page === modelData
                                             ? Font.DemiBold
                                             : Font.Normal
                            }
                        }

                        HoverHandler {
                            id: navHover
                        }

                        TapHandler {
                            onTapped: {
                                root.page = modelData

                                if (root.page === "library")
                                    root.applyLibraryFilter()

                                if (root.page === "playlists")
                                    musicBridge.refreshCollections()
                            }
                        }
                    }
                }
            }
        }
    }

    // AURA_NATIVE_MUSIC_LIQUID_GLASS_R8 subtle window frame
    Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        radius: 20
        color: "transparent"
        border.width: 1
        border.color: "#61DFF6"
        opacity: 0.22
        z: 9988
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 26
        anchors.rightMargin: 26
        height: 1
        color: "#B7F5FF"
        opacity: 0.18
        z: 9989
    }
}
