import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    objectName: "auraPremiumMemoryWorkspace"
    // AURA_MEMORY_FINAL_LAYOUT_FIX17
    // AURA_MEMORY_FINAL_POLISH_FIX16_R1_INT_HOTFIX
    property bool lightMode: false
    property string searchText: ""
    property bool clearConfirm: false
    AuraWorkspacePanel { anchors.fill: parent; z: -1; lightMode: root.lightMode }
    Item { anchors.fill: parent; z: 20
        Column { anchors.fill: parent; anchors.margins: 24; spacing: 14
            Row { width: parent.width; spacing: 14
                Column { width: parent.width - 190; spacing: 4
                    Text { text: "MÉMOIRE"; color: root.lightMode ? "#17394D" : "#D7F5FF"; font.pixelSize: 22; font.bold: true; font.letterSpacing: 1.2 }
                    Text { text: "Les informations que vous choisissez de conserver localement pour AURA."; color: root.lightMode ? "#607582" : "#91A6B5"; font.pixelSize: 10 }
                }
                Text { text: "MEMORY · AVAILABLE"; color: "#55D7A5"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
            }
            Text { text: "AJOUTER UN SOUVENIR"; color: root.lightMode ? "#24495B" : "#D7F5FF"; font.pixelSize: 11; font.bold: true }
            AuraTextArea { id: premiumMemoryInput; width: parent.width; height: 92; lightMode: root.lightMode; placeholderText: "Ex. Pour AURA, je préfère une interface très minimaliste..." }
            AuraButton { width: 132; variant: "primary"; lightMode: root.lightMode; text: "ENREGISTRER"; onClicked: { if (premiumMemoryInput.text.length > 0) { coreBridge.createMemory(premiumMemoryInput.text); premiumMemoryInput.text = "" } } }
            Row { width: parent.width; spacing: 8
                AuraTextField { id: premiumSearch; width: parent.width - 132; lightMode: root.lightMode; placeholderText: "⌕ Rechercher dans la mémoire locale" }
                AuraButton { width: 116; lightMode: root.lightMode; text: "RECHERCHER"; onClicked: { root.searchText = premiumSearch.text; coreBridge.searchMemories(premiumSearch.text) } }
            }
            Item { width: parent.width; height: Math.max(150, parent.height - 250)
                Column { anchors.centerIn: parent; spacing: 8; visible: coreBridge.memoryCount === 0
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "◈"; color: root.lightMode ? "#4A7890" : "#55D9F5"; font.pixelSize: 28 }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Aucun souvenir enregistré"; color: root.lightMode ? "#24495B" : "#D7F5FF"; font.pixelSize: 14; font.bold: true }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Les informations que vous choisissez de conserver apparaîtront ici."; color: root.lightMode ? "#607582" : "#91A6B5"; font.pixelSize: 10 }
                }
            }
        }
    }
    // AURA_MEMORY_CHROMIUM_PARITY_FIX15
    // AURA_MEMORY_FINAL_POLISH_FIX16

    function memoryTypeLabel(value) {
        var t = String(value || "").toLowerCase()
        if (t === "fact") return "FAIT"
        if (t === "preference") return "PRÉF."
        if (t === "project") return "PROJET"
        if (t === "goal") return "OBJECTIF"
        if (t === "habit") return "HABITUDE"
        if (t === "note") return "NOTE"
        return t.length ? t.toUpperCase() : "MÉMOIRE"
    }

    function compactDate(value) {
        var s = String(value || "")
        if (!s.length) return ""
        var m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
        if (!m) return s
        return m[3] + "/" + m[2] + "/" + m[1].slice(2) + " " + m[4] + ":" + m[5]
    }

    function typeValue(index) {
        return ["fact", "fact", "preference", "project", "goal", "habit"][Math.max(0, Math.min(5, index))]
    }

    function importanceValue(index) {
        return [3, 1, 2, 4, 5][Math.max(0, Math.min(4, index))]
    }

    Component.onCompleted: coreBridge.refreshMemories()
    onVisibleChanged: if (visible) coreBridge.refreshMemories()

    ContextDrawer {
        visible: false
        id: drawer
        lightMode: root.lightMode
        titleText: "MEMORY CORE"
        subtitleText: "Long-term local context"
        drawerWidth: 560
        accentColor: "#74EFFF"

        Rectangle {
            parent: drawer.headerActions
            width: 78
            height: 30
            radius: 8
            color: refreshHover.hovered
                   ? (root.lightMode ? "#ECFFFFFF" : "#14556F7D")
                   : (root.lightMode ? "#A8FFFFFF" : "#51030D16")
            border.width: 1
            border.color: refreshHover.hovered
                          ? "#5BA9BD"
                          : (root.lightMode ? "#335B8CA0" : "#27689BAD")

            Text {
                anchors.centerIn: parent
                text: "ACTUALISER"
                color: root.lightMode ? "#255A70" : "#8DE8F5"
                font.pixelSize: 7
                font.weight: Font.DemiBold
                font.letterSpacing: 0.55
            }

            HoverHandler { id: refreshHover }
            TapHandler { onTapped: coreBridge.refreshMemories() }
        }

        Column {
            parent: drawer.contentItem
            anchors.fill: parent
            spacing: 0

            // Chromium P0.6.2.6 status cards.
            Row {
                width: parent.width
                height: 72
                leftPadding: 12
                rightPadding: 12
                spacing: 7

                Repeater {
                    model: [
                        ["SOUVENIRS", String(coreBridge.memoryCount)],
                        ["MODE", coreBridge.memoryPrivateMode ? "PRIVÉ" : "NORMAL"],
                        ["CAPTURE", coreBridge.memoryPrivateMode
                                    ? "SUSPENDUE"
                                    : (coreBridge.memoryAutoCapture ? "ACTIVE" : "OFF")]
                    ]

                    delegate: Rectangle {
                        width: (parent.width - 38) / 3
                        height: 54
                        anchors.verticalCenter: parent.verticalCenter
                        radius: 9
                        color: root.lightMode ? "#AFFFFFFF" : "#86041019"
                        border.width: 1
                        border.color: root.lightMode ? "#245B899B" : "#2060A1B4"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 4

                            Text {
                                text: modelData[0]
                                color: root.lightMode ? "#67808D" : "#5E8294"
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.0
                            }

                            Text {
                                text: modelData[1]
                                color: modelData[1] === "PRIVÉ"
                                       ? "#C9A8DA"
                                       : (root.lightMode ? "#174A60" : "#C8F5FF")
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }

            // Search / sensitive toggle.
            Row {
                width: parent.width
                height: 44
                leftPadding: 12
                rightPadding: 12
                spacing: 8

                TextField {
                    width: Math.max(190, parent.width - 130)
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    placeholderText: "Rechercher dans la mémoire…"
                    text: root.searchText
                    onTextChanged: root.searchText = text
                    color: root.lightMode ? "#163B4E" : "#CFF5FF"
                    placeholderTextColor: root.lightMode ? "#718794" : "#607F91"
                    font.pixelSize: 10
                    leftPadding: 10
                    rightPadding: 10
                    selectionColor: "#315D8B9F"

                    background: Rectangle {
                        radius: 8
                        color: root.lightMode ? "#C7FFFFFF" : "#A6030D16"
                        border.width: 1
                        border.color: root.lightMode ? "#345B8B9E" : "#286899AB"
                    }
                }

                Rectangle {
                    width: 98
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 8
                    color: sensitiveHover.hovered
                           ? (root.lightMode ? "#E8FFFFFF" : "#15556F7D")
                           : (root.lightMode ? "#AFFFFFFF" : "#70040E18")
                    border.width: 1
                    border.color: coreBridge.showSensitiveMemories
                                  ? "#8D657F90"
                                  : (root.lightMode ? "#2D5A879B" : "#256899AB")

                    Row {
                        anchors.centerIn: parent
                        spacing: 6

                        Rectangle {
                            width: 8
                            height: 8
                            radius: 2
                            color: coreBridge.showSensitiveMemories ? "#C99AAF" : "transparent"
                            border.width: 1
                            border.color: coreBridge.showSensitiveMemories ? "#D8B2C2" : "#527382"
                        }

                        Text {
                            text: "SENSIBLES"
                            color: coreBridge.showSensitiveMemories
                                   ? "#D7A5B7"
                                   : (root.lightMode ? "#557887" : "#6F94A6")
                            font.pixelSize: 7
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                        }
                    }

                    HoverHandler { id: sensitiveHover }
                    TapHandler {
                        onTapped: coreBridge.setShowSensitiveMemories(!coreBridge.showSensitiveMemories)
                    }
                }
            }

            // Explicit memory creation.
            Rectangle {
                width: parent.width
                height: 126
                color: root.lightMode ? "#18FFFFFF" : "#24030D16"
                border.width: 1
                border.color: root.lightMode ? "#185B8799" : "#1469A7B6"

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 9
                    anchors.bottomMargin: 9
                    spacing: 7

                    TextArea {
                        id: memInput
                        width: parent.width
                        height: 62
                        enabled: !coreBridge.memoryPrivateMode
                        placeholderText: "Ajouter un souvenir explicite…"
                        wrapMode: TextArea.Wrap
                        color: root.lightMode ? "#173B4E" : "#C9F4FF"
                        placeholderTextColor: root.lightMode ? "#748A95" : "#607F91"
                        font.pixelSize: 10
                        leftPadding: 10
                        rightPadding: 10
                        topPadding: 8
                        bottomPadding: 8
                        selectionColor: "#315D8B9F"

                        background: Rectangle {
                            radius: 9
                            color: root.lightMode ? "#C7FFFFFF" : "#94030D16"
                            border.width: 1
                            border.color: root.lightMode ? "#345C8B9F" : "#286899AB"
                        }
                    }

                    Row {
                        width: parent.width
                        height: 31
                        spacing: 7

                        ComboBox {
                            id: memType
                            width: 152
                            height: 31
                            model: ["AUTO", "FAIT", "PRÉFÉRENCE", "PROJET", "OBJECTIF", "HABITUDE"]

                            contentItem: Text {
                                text: memType.displayText
                                color: root.lightMode ? "#345C6F" : "#89B8C9"
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 9
                                rightPadding: 22
                            }

                            indicator: Canvas {
                                x: memType.width - width - 8
                                y: (memType.height - height) / 2
                                width: 10
                                height: 6
                                onPaint: {
                                    var c=getContext("2d")
                                    c.clearRect(0,0,width,height)
                                    c.strokeStyle=root.lightMode?"#537687":"#739AA9"
                                    c.lineWidth=1
                                    c.beginPath()
                                    c.moveTo(1,1); c.lineTo(5,5); c.lineTo(9,1)
                                    c.stroke()
                                }
                            }

                            background: Rectangle {
                                radius: 8
                                color: root.lightMode ? "#D9FFFFFF" : "#B506141E"
                                border.width: 1
                                border.color: root.lightMode ? "#315A8095" : "#286899AB"
                            }

                            popup: Popup {
                                y: memType.height + 2
                                width: memType.width
                                implicitHeight: contentItem.implicitHeight + 8
                                padding: 4

                                background: Rectangle {
                                    radius: 8
                                    color: root.lightMode ? "#F9FCFD" : "#07141E"
                                    border.width: 1
                                    border.color: root.lightMode ? "#385E8093" : "#326D9CAE"
                                }

                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: memType.popup.visible ? memType.delegateModel : null
                                    currentIndex: memType.highlightedIndex
                                    ScrollIndicator.vertical: ScrollIndicator { }
                                }
                            }

                            delegate: ItemDelegate {
                                width: memType.width - 8
                                height: 28
                                contentItem: Text {
                                    text: modelData
                                    color: root.lightMode ? "#345C6F" : "#9ED4E0"
                                    font.pixelSize: 8
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: 5
                                    color: highlighted
                                           ? (root.lightMode ? "#E7F4F7" : "#123040")
                                           : "transparent"
                                }
                            }
                        }

                        ComboBox {
                            id: memImportance
                            width: 152
                            height: 31
                            model: ["IMPORTANCE 3", "IMPORTANCE 1", "IMPORTANCE 2", "IMPORTANCE 4", "IMPORTANCE 5"]

                            contentItem: Text {
                                text: memImportance.displayText
                                color: root.lightMode ? "#345C6F" : "#89B8C9"
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 9
                                rightPadding: 22
                            }

                            indicator: Canvas {
                                x: memImportance.width - width - 8
                                y: (memImportance.height - height) / 2
                                width: 10
                                height: 6
                                onPaint: {
                                    var c=getContext("2d")
                                    c.clearRect(0,0,width,height)
                                    c.strokeStyle=root.lightMode?"#537687":"#739AA9"
                                    c.lineWidth=1
                                    c.beginPath()
                                    c.moveTo(1,1); c.lineTo(5,5); c.lineTo(9,1)
                                    c.stroke()
                                }
                            }

                            background: Rectangle {
                                radius: 8
                                color: root.lightMode ? "#D9FFFFFF" : "#B506141E"
                                border.width: 1
                                border.color: root.lightMode ? "#315A8095" : "#286899AB"
                            }

                            popup: Popup {
                                y: memImportance.height + 2
                                width: memImportance.width
                                implicitHeight: contentItem.implicitHeight + 8
                                padding: 4

                                background: Rectangle {
                                    radius: 8
                                    color: root.lightMode ? "#F9FCFD" : "#07141E"
                                    border.width: 1
                                    border.color: root.lightMode ? "#385E8093" : "#326D9CAE"
                                }

                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: memImportance.popup.visible ? memImportance.delegateModel : null
                                    currentIndex: memImportance.highlightedIndex
                                    ScrollIndicator.vertical: ScrollIndicator { }
                                }
                            }

                            delegate: ItemDelegate {
                                width: memImportance.width - 8
                                height: 28
                                contentItem: Text {
                                    text: modelData
                                    color: root.lightMode ? "#345C6F" : "#9ED4E0"
                                    font.pixelSize: 8
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: 5
                                    color: highlighted
                                           ? (root.lightMode ? "#E7F4F7" : "#123040")
                                           : "transparent"
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width - 318
                            height: 31
                            radius: 8
                            color: retainHover.hovered
                                   ? (root.lightMode ? "#EAF8FAFC" : "#17556F7D")
                                   : (root.lightMode ? "#B8F4FBFC" : "#5C0C2636")
                            border.width: 1
                            border.color: root.lightMode ? "#405C94AA" : "#32709CAE"
                            opacity: coreBridge.memoryPrivateMode ? 0.38 : 1.0

                            Text {
                                anchors.centerIn: parent
                                text: "RETENIR"
                                color: root.lightMode ? "#275B70" : "#BAF3FF"
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.8
                            }

                            HoverHandler { id: retainHover }

                            TapHandler {
                                enabled: !coreBridge.memoryPrivateMode
                                onTapped: {
                                    var clean = memInput.text.trim()
                                    if (clean.length === 0)
                                        return
                                    if (coreBridge.createMemory(
                                                clean,
                                                root.typeValue(memType.currentIndex),
                                                root.importanceValue(memImportance.currentIndex))) {
                                        memInput.text = ""
                                        memType.currentIndex = 0
                                        memImportance.currentIndex = 0
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Recent injected context.
            Item {
                width: parent.width
                height: contextList.count === 0
                        ? 74
                        : Math.min(130, 39 + contextList.contentHeight)

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 8
                    spacing: 6

                    Row {
                        width: parent.width
                        height: 18

                        Text {
                            text: "CONTEXTE RÉCENT"
                            color: root.lightMode ? "#39768A" : "#77B8CA"
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Item { width: Math.max(8, parent.width - 278); height: 1 }

                        Text {
                            visible: contextList.count > 0
                            text: "Mémoires injectées récemment"
                            color: root.lightMode ? "#728895" : "#506F7E"
                            font.pixelSize: 7
                        }
                    }

                    ListView {
                        id: contextList
                        width: parent.width
                        height: contextList.count === 0
                                ? 32
                                : Math.min(92, contentHeight)
                        clip: true
                        spacing: 6
                        model: memoryContextModel

                        delegate: Rectangle {
                            width: contextList.width
                            height: 58
                            radius: 9
                            color: root.lightMode ? "#AFFFFFFF" : "#5A071520"
                            border.width: 1
                            border.color: root.lightMode ? "#2B71869C" : "#244F8194"

                            Column {
                                anchors.fill: parent
                                anchors.margins: 9
                                spacing: 4

                                Row {
                                    spacing: 7

                                    Text {
                                        text: root.memoryTypeLabel(memoryType)
                                        color: "#76C5D8"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    Text {
                                        visible: isSensitive
                                        text: "SENSIBLE"
                                        color: "#D7A5B7"
                                        font.pixelSize: 7
                                    }

                                    Item {
                                        width: Math.max(1, contextList.width - 230)
                                        height: 1
                                    }

                                    Text {
                                        text: "◆".repeat(Math.max(1, Math.min(5, importance)))
                                        color: "#768FB5"
                                        font.pixelSize: 7
                                    }
                                }

                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: content
                                    color: root.lightMode ? "#1B4357" : "#C7EEF7"
                                    font.pixelSize: 9
                                }
                            }
                        }

                    }

                    Text {
                        width: contextList.width
                        height: contextList.height
                        visible: contextList.count === 0
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        text: "Aucun souvenir injecté récemment."
                        color: root.lightMode ? "#667F8C" : "#698B98"
                        font.pixelSize: 8
                        font.letterSpacing: 0.2
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: root.lightMode ? "#1E5C8798" : "#17689AAB"
            }

            // Persistent memory consumes the remaining height.
            Item {
                width: parent.width
                height: Math.max(
                            140,
                            parent.height
                            - 72
                            - 44
                            - 126
                            - Math.min(130, 39 + contextList.contentHeight)
                            - 1
                            - 62)

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 8
                    anchors.bottomMargin: 7
                    spacing: 6

                    Row {
                        width: parent.width
                        height: 18

                        Text {
                            text: "MÉMOIRE PERSISTANTE"
                            color: root.lightMode ? "#39768A" : "#77B8CA"
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Item { width: Math.max(8, parent.width - 224); height: 1 }

                        Text {
                            text: memoryList.visibleCount + " souvenir" + (memoryList.visibleCount > 1 ? "s" : "")
                            color: root.lightMode ? "#718895" : "#506F7E"
                            font.pixelSize: 7
                        }
                    }

                    ListView {
                        id: memoryList
                        property int visibleCount: 0
                        width: parent.width
                        height: parent.height - 24
                        clip: true
                        spacing: 7
                        model: memoriesModel

                        function recount() {
                            var n = 0
                            for (var i=0; i<count; ++i) {
                                var item = itemAtIndex(i)
                                if (item && item.matchesSearch)
                                    n++
                            }
                            visibleCount = n
                        }

                        onCountChanged: Qt.callLater(recount)

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            width: 5
                        }

                        delegate: Rectangle {
                            id: memoryRow
                            readonly property bool matchesSearch:
                                root.searchText.length === 0
                                || (content + " " + memoryType + " " + sourceLabel)
                                   .toLowerCase()
                                   .indexOf(root.searchText.toLowerCase()) >= 0

                            visible: matchesSearch
                            width: memoryList.width - 3
                            height: visible ? 76 : 0
                            radius: 10
                            color: root.lightMode ? "#BFFFFFFF" : "#8C040F19"
                            border.width: 1
                            border.color: root.lightMode ? "#295B889B" : "#23628FA0"

                            onMatchesSearchChanged: Qt.callLater(memoryList.recount)
                            Component.onCompleted: Qt.callLater(memoryList.recount)

                            Column {
                                anchors.left: parent.left
                                anchors.right: deleteBtn.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: 10
                                anchors.rightMargin: 9
                                anchors.topMargin: 8
                                anchors.bottomMargin: 8
                                spacing: 4

                                Row {
                                    width: parent.width
                                    height: 12
                                    spacing: 7

                                    Text {
                                        text: root.memoryTypeLabel(memoryType)
                                        color: "#76C5D8"
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.55
                                    }

                                    Text {
                                        visible: isSensitive
                                        text: "SENSIBLE"
                                        color: "#D7A5B7"
                                        font.pixelSize: 7
                                    }

                                    Item { width: Math.max(1, parent.width - 196); height: 1 }

                                    Text {
                                        text: "◆".repeat(Math.max(1, Math.min(5, importance)))
                                        color: "#768FB5"
                                        font.pixelSize: 7
                                    }
                                }

                                Text {
                                    width: parent.width
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    text: content
                                    color: root.lightMode ? "#183E51" : "#C7EEF7"
                                    font.pixelSize: 9
                                    lineHeight: 1.28
                                }

                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: (sourceLabel.length ? sourceLabel : "local")
                                          + (createdAt.length ? " · " + root.compactDate(createdAt) : "")
                                          + (accessCount > 0 ? " · " + accessCount + "×" : "")
                                    color: root.lightMode ? "#718792" : "#5C7C8B"
                                    font.pixelSize: 7
                                }
                            }

                            Rectangle {
                                id: deleteBtn
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 26
                                height: 26
                                radius: 7
                                color: deleteHover.hovered ? "#31FF708F" : "#30500A18"
                                border.width: 1
                                border.color: deleteHover.hovered ? "#55FF708F" : "#2FFF708F"

                                Text {
                                    anchors.centerIn: parent
                                    text: "×"
                                    color: "#C98B9C"
                                    font.pixelSize: 12
                                }

                                HoverHandler { id: deleteHover }
                                TapHandler { onTapped: coreBridge.deleteMemory(itemId) }
                            }
                        }

                        Text {
                            visible: memoryList.count === 0
                            anchors.centerIn: parent
                            text: "Synchronisation du Core…"
                            color: root.lightMode ? "#6B8290" : "#57798A"
                            font.pixelSize: 9
                        }
                    }
                }
            }

            // Chromium footer.
            Item {
                width: parent.width
                height: 62

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: root.lightMode ? "#1E5C8798" : "#17689AAB"
                }

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 9
                    spacing: 7

                    Rectangle {
                        width: (parent.width - 7) / 2
                        height: 32
                        radius: 8
                        color: privateHover.hovered
                               ? (root.lightMode ? "#E8FFFFFF" : "#13556E7D")
                               : (root.lightMode ? "#BFFFFFFF" : "#7805121C")
                        border.width: 1
                        border.color: root.lightMode ? "#345B889B" : "#286899AB"

                        Text {
                            anchors.centerIn: parent
                            text: coreBridge.memoryPrivateMode
                                  ? "QUITTER LE MODE PRIVÉ"
                                  : "MODE PRIVÉ"
                            color: coreBridge.memoryPrivateMode
                                   ? "#C9A8DA"
                                   : (root.lightMode ? "#34677A" : "#9BD9E8")
                            font.pixelSize: 7
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                        }

                        HoverHandler { id: privateHover }
                        TapHandler {
                            onTapped: coreBridge.setMemoryPrivate(!coreBridge.memoryPrivateMode)
                        }
                    }

                    Rectangle {
                        width: (parent.width - 7) / 2
                        height: 32
                        radius: 8
                        color: root.clearConfirm
                               ? "#5B530A1C"
                               : (clearHover.hovered ? "#704A0C18" : "#60440916")
                        border.width: 1
                        border.color: clearHover.hovered ? "#55FF708F" : "#42FF708F"

                        Text {
                            anchors.centerIn: parent
                            text: root.clearConfirm ? "CONFIRMER EFFACER" : "EFFACER LE PROFIL"
                            color: root.lightMode ? "#8A4255" : "#D496A8"
                            font.pixelSize: 7
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                        }

                        HoverHandler { id: clearHover }

                        TapHandler {
                            onTapped: {
                                if (!root.clearConfirm) {
                                    root.clearConfirm = true
                                    clearTimer.restart()
                                } else {
                                    coreBridge.clearMemoryProfile("EFFACER")
                                    root.clearConfirm = false
                                }
                            }
                        }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 4
                    text: "Local SQLite · Les souvenirs sensibles sont masqués par défaut."
                    color: root.lightMode ? "#66818D" : "#7595A2"
                    font.pixelSize: 8
                    font.weight: Font.Medium
                }
            }
        }
    }

    Timer {
        id: clearTimer
        interval: 4000
        onTriggered: root.clearConfirm = false
    }
}
