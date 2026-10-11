import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import "../components"

Item {
    id: root
    property bool lightMode: false
    property int currentTab: 0
    // AURA_GOOGLE_PRODUCTIVITY_QT_FIX19
    // AURA_GOOGLE_ACCOUNT_CONNECT_FIX20
    // AURA_GOOGLE_BIDIRECTIONAL_FIX21
// AURA_GOOGLE_TASKS_WRITE_REPAIR_FIX22
    // AURA_PRODUCTIVITY_EDIT_ACTIONS_FIX23
    // AURA_PRODUCTIVITY_PREMIUM_DRAWERS_FIX25
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX26
    // AURA_PRODUCTIVITY_LAYOUT_GOOGLE_FIX28
    // AURA_GOOGLE_FAVICON_FIX29
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX27
    // AURA_CALENDAR_SELECTABLE_EDIT_FIX24
    property bool taskTargetGoogle: false
    property bool reminderTargetGoogle: false

    property string editGoogleTaskId: ""
    property string editGoogleTaskTitle: ""
    property string editGoogleTaskDue: ""
    property string editGoogleTaskOriginalDue: ""
    property bool editGoogleTaskDueEdited: false
    property string editLocalTaskId: ""
    property string editLocalTaskTitle: ""
    property string editLocalTaskDue: ""
    property string editNoteId: ""
    property bool editingNote: false

    property string editGoogleEventId: ""
    property string editGoogleEventTitle: ""
    property string editGoogleEventStart: ""
    property string editGoogleEventEnd: ""
    property string editGoogleEventDescription: ""

    FileDialog {
        id: googleOAuthDialog
        title: "Sélectionner le fichier OAuth Google"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Fichier OAuth Google (*.json)"]
        onAccepted: coreBridge.connectGoogle(selectedFile.toString())
    }

    function compactDate(value) {
        var s = String(value || "").trim()
        if (!s.length) return ""
        var m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/)
        if (!m) return s
        var out = m[3] + "/" + m[2] + "/" + m[1].slice(2)
        if (m[4] && m[5]) out += " " + m[4] + ":" + m[5]
        return out
    }
    function connectGoogleWorkspace() {
        if (coreBridge.googleOAuthClientStatus.configured) coreBridge.startGoogleWorkspaceOAuth()
        else googleOAuthDialog.open()
    }

    function statusLabel(value) {
        var s = String(value || "").toLowerCase()
        if (s === "done" || s === "completed") return "TERMINÉE"
        if (s === "needsaction" || s === "todo") return "À FAIRE"
        return s.length ? s.toUpperCase() : "À FAIRE"
    }

    function taskDueInput(value) {
        var s = String(value || "").trim()
        if (!s.length) return ""
        var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
        return m ? (m[1] + "-" + m[2] + "-" + m[3]) : s
    }

    function calendarInput(value) {
        var s = String(value || "").trim()
        if (!s.length) return ""
        var m = s.match(
            /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/
        )
        if (!m) return s
        var out = m[1] + "-" + m[2] + "-" + m[3]
        if (m[4] && m[5]) out += "T" + m[4] + ":" + m[5]
        return out
    }

    function beginGoogleTaskEdit(id, titleValue, dueValue) {
        editGoogleTaskId = String(id || "")
        editGoogleTaskTitle = String(titleValue || "")
        editGoogleTaskOriginalDue = String(dueValue || "")
        editGoogleTaskDue = taskDueInput(editGoogleTaskOriginalDue)
        editGoogleTaskDueEdited = false
    }

    function cancelGoogleTaskEdit() {
        editGoogleTaskId = ""
        editGoogleTaskTitle = ""
        editGoogleTaskDue = ""
        editGoogleTaskOriginalDue = ""
        editGoogleTaskDueEdited = false
    }

    function saveGoogleTaskEdit() {
        if (!editGoogleTaskId.length
                || !editGoogleTaskTitle.trim().length)
            return

        if (coreBridge.updateGoogleTask(
                    editGoogleTaskId,
                    editGoogleTaskTitle,
                    editGoogleTaskDue,
                    editGoogleTaskDueEdited)) {
            cancelGoogleTaskEdit()
        }
    }

    function beginLocalTaskEdit(id, titleValue, dueValue) {
        editLocalTaskId = String(id || "")
        editLocalTaskTitle = String(titleValue || "")
        editLocalTaskDue = taskDueInput(dueValue)
    }
    function saveLocalTaskEdit() {
        if (!editLocalTaskId.length || !editLocalTaskTitle.trim().length) return
        if (coreBridge.updateTask(editLocalTaskId, editLocalTaskTitle, editLocalTaskDue)) {
            editLocalTaskId = ""; editLocalTaskTitle = ""; editLocalTaskDue = ""
        }
    }

    function beginGoogleEventEdit(
        id,
        titleValue,
        startValue,
        endValue,
        descriptionValue
    ) {
        editGoogleEventId = String(id || "")
        editGoogleEventTitle = String(titleValue || "")
        editGoogleEventStart = calendarInput(startValue)
        editGoogleEventEnd = calendarInput(endValue)
        editGoogleEventDescription = String(descriptionValue || "")
    }

    function cancelGoogleEventEdit() {
        editGoogleEventId = ""
        editGoogleEventTitle = ""
        editGoogleEventStart = ""
        editGoogleEventEnd = ""
        editGoogleEventDescription = ""
    }

    function saveGoogleEventEdit() {
        if (!editGoogleEventId.length
                || !editGoogleEventTitle.trim().length
                || !editGoogleEventStart.trim().length)
            return

        if (coreBridge.updateGoogleEvent(
                    editGoogleEventId,
                    editGoogleEventTitle,
                    editGoogleEventStart,
                    editGoogleEventEnd,
                    editGoogleEventDescription)) {
            cancelGoogleEventEdit()
        }
    }

    function refreshTab() {
        coreBridge.refreshProductivity()
        if (currentTab === 0) coreBridge.refreshGoogleTasks()
    }

    Component.onCompleted: {
        console.log("TASKS_VIEW_INSTANCE_CREATED instance=auraNativeTasksView")
        refreshTab()
    }
    onVisibleChanged: if (visible) refreshTab()

    ContextDrawer {
        id: drawer
        lightMode: root.lightMode
        titleText: "PRODUCTIVITY CORE"
        subtitleText: "AURA + Google · Organisez, automatisez et restez aligné."
        drawerWidth: 980
        accentColor: "#74EFFF"
        premiumSurface: true
        headerHeight: 88
        titlePixelSize: 17
        subtitlePixelSize: 10

        Rectangle {
            parent: drawer.headerActions
            width: 154; height: 44; radius: 13
            color: syncHover.hovered ? "#8A12546C" : "#65102535"
            border.width: 1; border.color: syncHover.hovered ? "#8A74EFFF" : "#4B74DDEA"
            Text {
                anchors.centerIn: parent
                text: "SYNCHRONISER"
                color: "#8DE8F5"
                font.pixelSize: 9
                font.weight: Font.DemiBold
            }
            HoverHandler { id: syncHover }
            TapHandler { onTapped: root.refreshTab() }
        }

        Rectangle {
            parent: drawer.contentItem
            anchors.fill: parent
            anchors.margins: 12
            radius: 19
            color: "#3A06121D"
            border.width: 1
            border.color: "#2C6EDCEB"
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#580E2B40" }
                GradientStop { position: 0.42; color: "#3A091822" }
                GradientStop { position: 1.0; color: "#22030910" }
            }
        }

        Column {
            parent: drawer.contentItem
            anchors.fill: parent
            spacing: 0

            Row {
                width: parent.width
                height: 70
                leftPadding: 16
                rightPadding: 16
                spacing: 10

                Repeater {
                    model: ["TÂCHES", "RAPPELS", "NOTES", "CALENDRIER"]
                    delegate: Rectangle {
                        width: (parent.width - 62) / 4
                        height: 42
                        anchors.verticalCenter: parent.verticalCenter
                        radius: 12
                        color: root.currentTab === index ? "#8A145A72" : "#2C07121C"
                        border.width: 1
                        border.color: root.currentTab === index ? "#8874EFFF" : "#235B8498"
                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: root.currentTab === index ? "#B9F2FF" : "#5E8296"
                            font.pixelSize: root.currentTab === index ? 11 : 10
                            font.weight: root.currentTab === index ? Font.DemiBold : Font.Normal
                            font.letterSpacing: 0.8
                        }
                        Rectangle {
                            visible: root.currentTab === index
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 3
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width * 0.64
                            height: 2
                            radius: 1
                            color: "#74EFFF"
                            opacity: 0.88
                        }
                        TapHandler {
                            onTapped: {
                                if (index === 3) {
                                    bridge.setWorkspace("agenda")
                                } else {
                                    root.currentTab = index
                                    root.refreshTab()
                                }
                            }
                        }
                    }
                }
            }

            Rectangle { width: parent.width; height: 1; color: "#1468D3E6" }

            Flickable {
                visible: root.currentTab === 0
                width: parent.width
                height: parent.height - 71
                contentWidth: width
                contentHeight: taskBody.implicitHeight + 24
                clip: true
                ScrollBar.vertical: ScrollBar { width: 3; opacity: active ? 0.68 : 0.18 }

                Column {
                    id: taskBody
                    width: parent.width - 40
                    x: 20; y: 20
                    spacing: 12

                    Row {
                        width: parent.width
                        height: 34
                        spacing: 10

                        Text {
                            width: 82
                            anchors.verticalCenter: parent.verticalCenter
                            text: "CRÉER DANS"
                            color: "#5E8296"
                            font.pixelSize: 8
                            font.letterSpacing: 0.8
                        }
                        Rectangle {
                            objectName: "taskCreateTargetLocal"
                            width: 124; height: 34; radius: 11
                            color: !root.taskTargetGoogle ? "#4B237497" : "transparent"
                            border.width: 1
                            border.color: !root.taskTargetGoogle ? "#2B74DCEC" : "#1B527889"
                            Text { anchors.centerIn: parent; text: "AURA LOCAL"; color: !root.taskTargetGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                            TapHandler { onTapped: root.taskTargetGoogle = false }
                        }
                        Rectangle {
                            objectName: "taskCreateTargetGoogle"
                            width: 124; height: 34; radius: 11
                            enabled: coreBridge.googleWorkspaceStatus === "connected"
                            opacity: enabled ? 1 : 0.45
                            color: root.taskTargetGoogle ? "#4B237497" : "transparent"
                            border.width: 1
                            border.color: root.taskTargetGoogle ? "#2B74DCEC" : "#1B527889"
                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Image {
                                    width: 14; height: 14
                                    source: "../assets/google_favicon.png"
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                                Text { text: "GOOGLE"; color: root.taskTargetGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                            }
                            TapHandler { enabled: parent.enabled; onTapped: root.taskTargetGoogle = true }
                        }
                    }

                    Row {
                        width: parent.width
                        height: 42
                        spacing: 10
                        TextField {
                            id: taskTitle
                            width: parent.width - 222
                            height: 40
                            placeholderText: root.taskTargetGoogle ? "Nouvelle Google Task…" : "Nouvelle tâche AURA…"
                            color: "#C7F3FF"
                            placeholderTextColor: "#607F91"
                            font.pixelSize: 9
                            leftPadding: 9; rightPadding: 9
                            background: Rectangle {
                                radius: 10; color: "#98030D16"
                                border.width: 1; border.color: "#236BD8EA"
                            }
                            Keys.onReturnPressed: root.addTask()
                        }
                        TextField {
                            id: taskDue
                            width: 160
                            height: 40
                            placeholderText: root.taskTargetGoogle ? "YYYY-MM-DD" : "Échéance"
                            color: "#C7F3FF"
                            placeholderTextColor: "#607F91"
                            font.pixelSize: 9
                            leftPadding: 9; rightPadding: 9
                            background: Rectangle {
                                radius: 10; color: "#98030D16"
                                border.width: 1; border.color: "#236BD8EA"
                            }
                            Keys.onReturnPressed: root.addTask()
                        }
                        Rectangle {
                            width: 42; height: 40; radius: 12
                            color: addTaskHover.hovered ? "#235FE7F5" : "#5C0D2636"
                            border.width: 1; border.color: "#2C72DFF0"
                            Text { anchors.centerIn: parent; text: "+"; color: "#AEEFFF"; font.pixelSize: 14 }
                            HoverHandler { id: addTaskHover }
                            TapHandler { onTapped: root.addTask() }
                        }
                    }

                    Rectangle {
                        width: parent.width; height: 68; radius: 16
                        color: "#8A071D2B"
                        border.width: 1
                        border.color: coreBridge.googleSyncActive ? "#4074EFFF" : "#2B5D7585"
                        Column {
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 3
                            Text {
                                text: "TÂCHES · AURA + GOOGLE TASKS"
                                color: "#D8F9FF"; font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: coreBridge.googleTasksStatus
                                color: coreBridge.googleSyncActive ? "#6EA7B8" : "#B27B8B"
                                font.pixelSize: 8
                            }
                        }
                    }

                    Rectangle {
                        visible: coreBridge.googleWorkspaceStatus !== "connected"
                        width: parent.width
                        height: visible ? 32 : 0
                        radius: 10
                        color: googleConnectHover.hovered ? "#235FE7F5" : "#5C0D2636"
                        border.width: 1
                        border.color: "#3270DDEA"
                        Text {
                            anchors.centerIn: parent
                            text: coreBridge.googleConnectButtonLabel
                            color: "#AEEFFF"
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                        }
                        HoverHandler { id: googleConnectHover }
                        TapHandler {
                            enabled: !coreBridge.googleConnecting
                            onTapped: root.connectGoogleWorkspace()
                        }
                    }

                    Rectangle {
                        visible: root.editGoogleTaskId.length > 0 || root.editLocalTaskId.length > 0
                        width: parent.width
                        height: visible ? 78 : 0
                        radius: 10
                        color: "#7805121D"
                        border.width: 1
                        border.color: "#3474DDEC"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6

                            Row {
                                width: parent.width
                                height: 28
                                spacing: 6

                                TextField {
                                    width: parent.width - 128
                                    height: 28
                                    text: root.editGoogleTaskId.length > 0 ? root.editGoogleTaskTitle : root.editLocalTaskTitle
                                    placeholderText: root.editGoogleTaskId.length > 0 ? "Titre Google Task" : "Titre tâche AURA"
                                    color: "#D7F7FF"
                                    placeholderTextColor: "#607F91"
                                    font.pixelSize: 9
                                    leftPadding: 8
                                    rightPadding: 8
                                    onTextChanged:
                                        if (root.editGoogleTaskId.length > 0) root.editGoogleTaskTitle = text
                                        else root.editLocalTaskTitle = text
                                    background: Rectangle {
                                        radius: 7
                                        color: "#A604101A"
                                        border.width: 1
                                        border.color: "#286ED9EA"
                                    }
                                }

                                TextField {
                                    width: 122
                                    height: 28
                                    text: root.editGoogleTaskId.length > 0 ? root.editGoogleTaskDue : root.editLocalTaskDue
                                    placeholderText: "YYYY-MM-DD"
                                    color: "#D7F7FF"
                                    placeholderTextColor: "#607F91"
                                    font.pixelSize: 9
                                    leftPadding: 8
                                    rightPadding: 8
                                    onTextChanged: {
                                        if (root.editGoogleTaskId.length > 0) {
                                            if (text !== root.taskDueInput(root.editGoogleTaskOriginalDue)) root.editGoogleTaskDueEdited = true
                                            root.editGoogleTaskDue = text
                                        } else root.editLocalTaskDue = text
                                    }
                                    background: Rectangle {
                                        radius: 7
                                        color: "#A604101A"
                                        border.width: 1
                                        border.color: "#286ED9EA"
                                    }
                                }
                            }

                            Row {
                                width: parent.width
                                height: 28
                                spacing: 6

                                Item {
                                    width: parent.width - 166
                                    height: 1
                                }

                                Rectangle {
                                    width: 78
                                    height: 26
                                    radius: 7
                                    color: saveTaskEditHover.hovered
                                           ? "#275FE7F5"
                                           : "#62102B3A"
                                    border.width: 1
                                    border.color: "#3275DDEB"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "ENREGISTRER"
                                        color: "#B8F4FF"
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                    HoverHandler {
                                        id: saveTaskEditHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.editGoogleTaskId.length > 0 ? root.saveGoogleTaskEdit() : root.saveLocalTaskEdit()
                                    }
                                }

                                Rectangle {
                                    width: 76
                                    height: 26
                                    radius: 7
                                    color: cancelTaskEditHover.hovered
                                           ? "#243A5668"
                                           : "#4B07131C"
                                    border.width: 1
                                    border.color: "#26556F7D"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "ANNULER"
                                        color: "#7695A4"
                                        font.pixelSize: 8
                                    }
                                    HoverHandler {
                                        id: cancelTaskEditHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.editGoogleTaskId.length > 0 ? root.cancelGoogleTaskEdit() : (root.editLocalTaskId = "")
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width; height: 18
                        Text { text: "GOOGLE TASKS"; color: "#77B8CA"; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Item { width: parent.width - 170; height: 1 }
                        Text { text: coreBridge.googleTasksCount + " tâche(s)"; color: "#506F7E"; font.pixelSize: 8 }
                    }

                    Text {
                        visible: coreBridge.googleTasksCount === 0
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: coreBridge.googleTasksStatus.indexOf("réautorisation") >= 0
                              ? coreBridge.googleTasksStatus
                              : (coreBridge.googleSyncActive
                                 ? "Aucune tâche Google active."
                                 : coreBridge.googleTasksStatus)
                        color: "#5E8190"; font.pixelSize: 9
                    }

                    Repeater {
                        model: coreBridge.googleTasks
                        delegate: Rectangle {
                            property var googleTask: modelData || ({})
                            width: taskBody.width; height: 74; radius: 14
                            color: "#B30A1925"; border.width: 1; border.color: "#3674DFF0"
                            Row {
                                anchors.fill: parent; anchors.margins: 14; spacing: 10
                                Rectangle {
                                    width: 76; height: 24; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: "#34143A48"; border.width: 1; border.color: "#3474DDEC"
                                    Row {
                                        anchors.centerIn: parent
                                        spacing: 5
                                        Image {
                                            width: 13; height: 13
                                            source: "../assets/google_favicon.png"
                                            fillMode: Image.PreserveAspectFit
                                            smooth: true
                                        }
                                        Text { text: "GOOGLE"; color: "#83E6F5"; font.pixelSize: 8 }
                                    }
                                }
                                Column {
                                    width: parent.width - 252
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    Text {
                                        width: parent.width; elide: Text.ElideRight
                                        text: String(googleTask.title || ""); color: "#C7F2FB"; font.pixelSize: 11; font.weight: Font.DemiBold
                                    }
                                    Text {
                                        width: parent.width; elide: Text.ElideRight
                                        text: root.statusLabel(googleTask.status) + (String(googleTask.due || "").length ? " · " + root.compactDate(googleTask.due) : "")
                                        color: "#607F91"; font.pixelSize: 8
                                    }
                                }
                                Rectangle {
                                    width: 38
                                    height: 38
                                    radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: gEditHover.hovered
                                           ? "#245EE8F5"
                                           : "#4A071520"
                                    border.width: 1
                                    border.color: "#2B6EDBEA"
                                    PencilIcon {
                                        anchors.centerIn: parent
                                        width: 21
                                        height: 21
                                        iconColor: "#8FEAF5"
                                        detailColor: "#D7FBFF"
                                    }
                                    ToolTip.visible: gEditHover.hovered
                                    ToolTip.text: "Modifier"
                                    ToolTip.delay: 350
                                    HoverHandler {
                                        id: gEditHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.beginGoogleTaskEdit(
                                                String(googleTask.id || ""),
                                                String(googleTask.title || ""),
                                                String(googleTask.due || "")
                                            )
                                    }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: gDoneHover.hovered ? "#1E66FFD1" : "#4A05121C"
                                    border.width: 1; border.color: "#2B6EDBC3"
                                    Text { anchors.centerIn: parent; text: "✓"; color: "#72CADA"; font.pixelSize: 13 }
                                    HoverHandler { id: gDoneHover }
                                    TapHandler { onTapped: coreBridge.completeGoogleTask(String(googleTask.id || "")) }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: gDeleteHover.hovered ? "#31FF708F" : "#30500A18"
                                    border.width: 1; border.color: "#2FFF708F"
                                    Text { anchors.centerIn: parent; text: "×"; color: "#C98B9C"; font.pixelSize: 14 }
                                    HoverHandler { id: gDeleteHover }
                                    TapHandler { onTapped: coreBridge.deleteGoogleTask(String(googleTask.id || ""), String(googleTask.title || "")) }
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#0F527B8C" }

                    Row {
                        width: parent.width; height: 18
                        Text { text: "AURA LOCAL"; color: "#77B8CA"; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Item { width: parent.width - 155; height: 1 }
                        Text { text: String(Number(coreBridge.taskCount || 0)) + " tâche(s)"; color: "#506F7E"; font.pixelSize: 8 }
                    }

                    Repeater {
                        model: tasksModel
                        delegate: Rectangle {
                            id: localTask
                            width: taskBody.width; height: 74; radius: 14
                            property bool done: String(status).toUpperCase() === "DONE"
                            Component.onCompleted: console.log("LOCAL_TASK_DELEGATE index=" + index
                                + " id_present=" + (String(itemId || "").length > 0)
                                + " title_present=" + (String(title || "").trim().length > 0)
                                + " status=" + (String(status || "unknown") || "unknown")
                                + " due_present=" + (String(dueDate || "").length > 0))
                            color: "#9405111B"; border.width: 1; border.color: "#236CD8E8"
                            opacity: done ? 0.75 : 1
                            Row {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                height: 38
                                spacing: 10
                                Rectangle {
                                    width: 58; height: 22; radius: 11
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: done ? "#32154034" : "#3D143249"
                                    border.width: 1; border.color: done ? "#3A60C89C" : "#3172DCEC"
                                    Text { anchors.centerIn: parent; text: "AURA"; color: done ? "#61CA9B" : "#83E6F5"; font.pixelSize: 8 }
                                }
                                Column {
                                    // Match the action column geometry: 14px card
                                    // margins, 12px gaps, and a 38px action button.
                                    width: parent.width - (done ? 158 : 208)
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    Text {
                                        width: parent.width; elide: Text.ElideRight
                                        text: title; color: "#C7F2FB"; font.pixelSize: 9
                                        font.weight: Font.DemiBold; font.strikeout: done
                                    }
                                    Text {
                                        text: root.statusLabel(status) + (String(dueDate).length ? " · " + root.compactDate(dueDate) : "")
                                        color: "#607F91"; font.pixelSize: 8
                                    }
                                }
                                Rectangle {
                                    width: 38
                                    height: 38
                                    radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: localEditHover.hovered ? "#245EE8F5" : "#4A071520"
                                    border.width: 1
                                    border.color: "#2B6EDBEA"
                                    PencilIcon {
                                        anchors.centerIn: parent
                                        width: 21
                                        height: 21
                                        iconColor: "#8FEAF5"
                                        detailColor: "#D7FBFF"
                                    }
                                    ToolTip.visible: localEditHover.hovered
                                    ToolTip.text: "Modifier"
                                    ToolTip.delay: 350
                                    HoverHandler { id: localEditHover }
                                    TapHandler { onTapped: root.beginLocalTaskEdit(String(itemId || ""), String(title || ""), String(dueDate || "")) }
                                }
                                Rectangle {
                                    visible: !done
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: completeHover.hovered ? "#1E66FFD1" : "#4A05121C"
                                    border.width: 1; border.color: "#2B6EDBC3"
                                    Text { anchors.centerIn: parent; text: "✓"; color: "#72CADA"; font.pixelSize: 13 }
                                    HoverHandler { id: completeHover }
                                    TapHandler { onTapped: coreBridge.completeTask(String(itemId)) }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: localDeleteHover.hovered ? "#31FF708F" : "#30500A18"
                                    border.width: 1; border.color: "#2FFF708F"
                                    Text { anchors.centerIn: parent; text: "×"; color: "#C98B9C"; font.pixelSize: 14 }
                                    HoverHandler { id: localDeleteHover }
                                    TapHandler { onTapped: coreBridge.deleteTask(String(itemId)) }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                visible: root.currentTab === 1
                width: parent.width
                height: parent.height - 71
                contentWidth: width
                contentHeight: reminderBody.implicitHeight + 24
                clip: true
                ScrollBar.vertical: ScrollBar { width: 3; opacity: active ? 0.68 : 0.18 }

                Column {
                    id: reminderBody
                    width: parent.width - 40
                    x: 20; y: 20
                    spacing: 12

                    Row {
                        width: parent.width; height: 28; spacing: 7
                        Text { width: 74; anchors.verticalCenter: parent.verticalCenter; text: "CRÉER DANS"; color: "#5E8296"; font.pixelSize: 8; font.letterSpacing: 0.8 }
                        Rectangle {
                            objectName: "reminderCreateTargetLocal"
                            width: 92; height: 24; radius: 7
                            color: !root.reminderTargetGoogle ? "#4B237497" : "transparent"
                            border.width: 1; border.color: !root.reminderTargetGoogle ? "#2B74DCEC" : "#1B527889"
                            Text { anchors.centerIn: parent; text: "AURA RAPPEL"; color: !root.reminderTargetGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                            TapHandler { onTapped: root.reminderTargetGoogle = false }
                        }
                        Rectangle {
                            objectName: "reminderCreateTargetGoogle"
                            width: 112; height: 24; radius: 7
                            enabled: coreBridge.googleWorkspaceStatus === "connected"
                            opacity: enabled ? 1 : 0.45
                            color: root.reminderTargetGoogle ? "#4B237497" : "transparent"
                            border.width: 1; border.color: root.reminderTargetGoogle ? "#2B74DCEC" : "#1B527889"
                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Image { width: 14; height: 14; source: "../assets/google_favicon.png"; fillMode: Image.PreserveAspectFit; smooth: true }
                                Text { text: "GOOGLE CALENDAR"; color: root.reminderTargetGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                            }
                            TapHandler { enabled: parent.enabled; onTapped: root.reminderTargetGoogle = true }
                        }
                    }

                    Row {
                        width: parent.width; height: 40; spacing: 10
                        TextField {
                            id: reminderText
                            width: Math.max(40, parent.width - 141 - 42 - 20); height: 32
                            anchors.verticalCenter: parent.verticalCenter
                            placeholderText: root.reminderTargetGoogle ? "Nouvel événement Google…" : "Nouveau rappel AURA…"
                            color: "#C7F3FF"; placeholderTextColor: "#607F91"; font.pixelSize: 9
                            leftPadding: 9; rightPadding: 9
                            background: Rectangle { radius: 10; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                        }
                        TextField {
                            id: reminderWhen
                            width: 141; height: 32
                            anchors.verticalCenter: parent.verticalCenter
                            placeholderText: "YYYY-MM-DDTHH:MM"
                            color: "#C7F3FF"; placeholderTextColor: "#607F91"; font.pixelSize: 9
                            leftPadding: 9; rightPadding: 9
                            background: Rectangle { radius: 10; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                        }
                        Rectangle {
                            width: 42; height: 32; radius: 10
                            anchors.verticalCenter: parent.verticalCenter
                            color: remAddHover.hovered ? "#235FE7F5" : "#5C0D2636"
                            border.width: 1; border.color: "#2C72DFF0"
                            Text { anchors.centerIn: parent; text: "+"; color: "#AEEFFF"; font.pixelSize: 14 }
                            HoverHandler { id: remAddHover }
                            TapHandler {
                                onTapped: {
                                    var ok = root.reminderTargetGoogle
                                             ? coreBridge.createGoogleEvent(reminderText.text, reminderWhen.text, "", "")
                                             : coreBridge.createReminder(reminderText.text, reminderWhen.text)
                                    if (ok) {
                                        reminderText.text = ""; reminderWhen.text = ""
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width; height: 18
                        Text { text: "RAPPELS AURA"; color: "#77B8CA"; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Item { width: parent.width - 170; height: 1 }
                        Text { text: String(remindersModel.count || 0) + " rappel(s)"; color: "#506F7E"; font.pixelSize: 8 }
                    }

                    Repeater {
                        model: remindersModel
                        delegate: Rectangle {
                            Component.onCompleted: console.log("LOCAL_REMINDER_DELEGATE index=" + index
                                + " id_present=" + (String(itemId || "").length > 0)
                                + " trigger_present=" + (String(triggerAt || "").length > 0))
                            width: reminderBody.width; height: 74; radius: 14
                            color: "#9405111B"; border.width: 1; border.color: "#236CD8E8"
                            Row {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                height: 38
                                spacing: 12
                                Rectangle {
                                    width: 58; height: 22; radius: 11
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: "#3D143249"; border.width: 1; border.color: "#3172DCEC"
                                    Text { anchors.centerIn: parent; text: "AURA"; color: "#83E6F5"; font.pixelSize: 8 }
                                }
                                Column {
                                    width: parent.width - 120
                                    anchors.verticalCenter: parent.verticalCenter; spacing: 4
                                    Text { width: parent.width; elide: Text.ElideRight; text: content; color: "#C7F2FB"; font.pixelSize: 11; font.weight: Font.DemiBold }
                                    Text { text: root.compactDate(triggerAt); color: "#607F91"; font.pixelSize: 8 }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: delRemHover.hovered ? "#31FF708F" : "#30500A18"
                                    border.width: 1; border.color: "#2FFF708F"
                                    Text { anchors.centerIn: parent; text: "×"; color: "#C98B9C"; font.pixelSize: 14 }
                                    HoverHandler { id: delRemHover }
                            TapHandler { onTapped: coreBridge.deleteReminder(String(itemId || ""), String(content || "")) }
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#0F527B8C" }

                    Rectangle {
                        visible: root.editGoogleEventId.length > 0
                        width: parent.width
                        height: visible ? 108 : 0
                        radius: 10
                        color: "#7805121D"
                        border.width: 1
                        border.color: "#3474DDEC"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 6

                            TextField {
                                width: parent.width
                                height: 28
                                text: root.editGoogleEventTitle
                                placeholderText: "Titre Google Calendar"
                                color: "#D7F7FF"
                                placeholderTextColor: "#607F91"
                                font.pixelSize: 9
                                leftPadding: 8
                                rightPadding: 8
                                onTextChanged:
                                    root.editGoogleEventTitle = text
                                background: Rectangle {
                                    radius: 7
                                    color: "#A604101A"
                                    border.width: 1
                                    border.color: "#286ED9EA"
                                }
                            }

                            Row {
                                width: parent.width
                                height: 28
                                spacing: 6

                                TextField {
                                    width: (parent.width - 6) / 2
                                    height: 28
                                    text: root.editGoogleEventStart
                                    placeholderText:
                                        "Début YYYY-MM-DDTHH:MM"
                                    color: "#D7F7FF"
                                    placeholderTextColor: "#607F91"
                                    font.pixelSize: 9
                                    leftPadding: 8
                                    rightPadding: 8
                                    onTextChanged:
                                        root.editGoogleEventStart = text
                                    background: Rectangle {
                                        radius: 7
                                        color: "#A604101A"
                                        border.width: 1
                                        border.color: "#286ED9EA"
                                    }
                                }

                                TextField {
                                    width: (parent.width - 6) / 2
                                    height: 28
                                    text: root.editGoogleEventEnd
                                    placeholderText:
                                        "Fin YYYY-MM-DDTHH:MM"
                                    color: "#D7F7FF"
                                    placeholderTextColor: "#607F91"
                                    font.pixelSize: 9
                                    leftPadding: 8
                                    rightPadding: 8
                                    onTextChanged:
                                        root.editGoogleEventEnd = text
                                    background: Rectangle {
                                        radius: 7
                                        color: "#A604101A"
                                        border.width: 1
                                        border.color: "#286ED9EA"
                                    }
                                }
                            }

                            Row {
                                width: parent.width
                                height: 28
                                spacing: 6

                                Item {
                                    width: parent.width - 166
                                    height: 1
                                }

                                Rectangle {
                                    width: 78
                                    height: 26
                                    radius: 7
                                    color: saveEventHover.hovered
                                           ? "#275FE7F5"
                                           : "#62102B3A"
                                    border.width: 1
                                    border.color: "#3275DDEB"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "ENREGISTRER"
                                        color: "#B8F4FF"
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                    HoverHandler {
                                        id: saveEventHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.saveGoogleEventEdit()
                                    }
                                }

                                Rectangle {
                                    width: 76
                                    height: 26
                                    radius: 7
                                    color: cancelEventHover.hovered
                                           ? "#243A5668"
                                           : "#4B07131C"
                                    border.width: 1
                                    border.color: "#26556F7D"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "ANNULER"
                                        color: "#7695A4"
                                        font.pixelSize: 8
                                    }
                                    HoverHandler {
                                        id: cancelEventHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.cancelGoogleEventEdit()
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width; height: 18
                        Text { text: "GOOGLE CALENDAR · CE MOIS"; color: "#77B8CA"; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Item { width: parent.width - 230; height: 1 }
                        Text { text: coreBridge.googleCalendarCount + " événement(s)"; color: "#506F7E"; font.pixelSize: 8 }
                    }

                    Repeater {
                        model: googleCalendarModel
                        delegate: Rectangle {
                            width: reminderBody.width; height: 70; radius: 12
                            color: "#83040F19"; border.width: 1; border.color: "#2369D5E7"
                            Row {
                                anchors.fill: parent; anchors.margins: 14; spacing: 12
                                Rectangle {
                                    width: 76; height: 24; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: "#34143A48"; border.width: 1; border.color: "#3474DDEC"
                                    Row {
                                        anchors.centerIn: parent
                                        spacing: 5
                                        Image {
                                            width: 13; height: 13
                                            source: "../assets/google_favicon.png"
                                            fillMode: Image.PreserveAspectFit
                                            smooth: true
                                        }
                                        Text { text: "GOOGLE"; color: "#83E6F5"; font.pixelSize: 8 }
                                    }
                                }
                                Column {
                                    width: parent.width - 147
                                    anchors.verticalCenter: parent.verticalCenter; spacing: 4
                                    Text { width: parent.width; elide: Text.ElideRight; text: title; color: "#C7F2FB"; font.pixelSize: 11; font.weight: Font.DemiBold }
                                    Text { width: parent.width; elide: Text.ElideRight; text: root.compactDate(triggerAt) + (String(description).length ? " · " + description : ""); color: "#607F91"; font.pixelSize: 8 }
                                }
                                Rectangle {
                                    width: 38
                                    height: 38
                                    radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: gCalEditHover.hovered
                                           ? "#245EE8F5"
                                           : "#4A071520"
                                    border.width: 1
                                    border.color: "#2B6EDBEA"
                                    PencilIcon {
                                        anchors.centerIn: parent
                                        width: 21
                                        height: 21
                                        iconColor: "#8FEAF5"
                                        detailColor: "#D7FBFF"
                                    }
                                    ToolTip.visible: gCalEditHover.hovered
                                    ToolTip.text: "Modifier"
                                    ToolTip.delay: 350
                                    HoverHandler {
                                        id: gCalEditHover
                                    }
                                    TapHandler {
                                        onTapped:
                                            root.beginGoogleEventEdit(
                                                String(externalId),
                                                String(title),
                                                String(triggerAt),
                                                String(endAt),
                                                String(description)
                                            )
                                    }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: gCalDeleteHover.hovered ? "#31FF708F" : "#30500A18"
                                    border.width: 1; border.color: "#2FFF708F"
                                    Text { anchors.centerIn: parent; text: "×"; color: "#C98B9C"; font.pixelSize: 14 }
                                    HoverHandler { id: gCalDeleteHover }
                                    TapHandler { onTapped: coreBridge.deleteGoogleEvent(String(externalId)) }
                                }
                            }
                        }
                    }
                }
            }

            Flickable {
                visible: root.currentTab === 2
                width: parent.width
                height: parent.height - 71
                contentWidth: width
                contentHeight: noteBody.implicitHeight + 24
                clip: true
                ScrollBar.vertical: ScrollBar { width: 3; opacity: active ? 0.68 : 0.18 }

                Column {
                    id: noteBody
                    width: parent.width - 40
                    x: 20; y: 20
                    spacing: 12

                    Rectangle {
                        width: parent.width; height: 62; radius: 12
                        color: "#61031520"; border.width: 1; border.color: "#245B889B"
                        Column {
                            anchors.fill: parent; anchors.margins: 12; spacing: 4
                            Text { text: "NOTES · AURA LOCAL"; color: "#C6F4FF"; font.pixelSize: 11; font.weight: Font.DemiBold }
                            Text {
                                width: parent.width; elide: Text.ElideRight
                                text: "Google Keep n’est pas exposé par le Core AURA actuel."
                                color: "#627F90"; font.pixelSize: 8
                            }
                        }
                    }

                    TextField {
                        id: noteTitle
                        width: parent.width; height: 32
                        placeholderText: "Titre (optionnel)"
                        color: "#C7F3FF"; placeholderTextColor: "#607F91"; font.pixelSize: 9
                        leftPadding: 9; rightPadding: 9
                        background: Rectangle { radius: 10; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                    }

                    TextArea {
                        id: noteContent
                        width: parent.width; height: 92
                        placeholderText: "Écrire une note…"
                        wrapMode: TextArea.Wrap
                        color: "#C7F3FF"; placeholderTextColor: "#607F91"; font.pixelSize: 9
                        leftPadding: 9; rightPadding: 9; topPadding: 8; bottomPadding: 8
                        background: Rectangle { radius: 10; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                    }

                    Rectangle {
                        width: parent.width; height: 32; radius: 10
                        color: noteSaveHover.hovered ? "#1D5BE1EF" : "#580A2432"
                        border.width: 1; border.color: "#2B70DDEB"
                        Text { anchors.centerIn: parent; text: root.editingNote ? "ENREGISTRER LA NOTE" : "ENREGISTRER DANS AURA"; color: "#AEEFFF"; font.pixelSize: 8; font.weight: Font.DemiBold }
                        HoverHandler { id: noteSaveHover }
                        TapHandler {
                            onTapped: {
                                var ok = root.editingNote ? coreBridge.updateNote(root.editNoteId, noteTitle.text, noteContent.text) : coreBridge.createNote(noteTitle.text, noteContent.text)
                                if (ok) {
                                    noteTitle.text = ""; noteContent.text = ""
                                    root.editNoteId = ""; root.editingNote = false
                                }
                            }
                        }
                    }

                    Row {
                        width: parent.width; height: 18
                        Text { text: "NOTES LOCALES"; color: "#77B8CA"; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Item { width: parent.width - 160; height: 1 }
                        Text { text: String(notesModel.count || 0) + " note(s)"; color: "#506F7E"; font.pixelSize: 8 }
                    }

                    Repeater {
                        model: notesModel
                        delegate: Rectangle {
                            width: noteBody.width; height: 70; radius: 10
                            color: "#9405111B"; border.width: 1; border.color: "#236CD8E8"
                            Row {
                                anchors.fill: parent; anchors.margins: 14; spacing: 12
                                Column {
                                    width: parent.width - 40
                                    anchors.verticalCenter: parent.verticalCenter; spacing: 4
                                    Text { width: parent.width; elide: Text.ElideRight; text: String(title).length ? title : "Note"; color: "#C7F2FB"; font.pixelSize: 11; font.weight: Font.DemiBold }
                                    Text { width: parent.width; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; text: content; color: "#607F91"; font.pixelSize: 8 }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: delNoteHover.hovered ? "#31FF708F" : "#30500A18"
                                    border.width: 1; border.color: "#2FFF708F"
                                    Text { anchors.centerIn: parent; text: "×"; color: "#C98B9C"; font.pixelSize: 14 }
                                    HoverHandler { id: delNoteHover }
                                    TapHandler { onTapped: coreBridge.deleteNote(String(itemId || ""), String(title || "")) }
                                }
                                Rectangle {
                                    width: 38; height: 38; radius: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: editNoteHover.hovered ? "#1D5BE1EF" : "#20315B70"
                                    border.width: 1; border.color: "#2B70DDEB"
                                    Text { anchors.centerIn: parent; text: "✎"; color: "#8FE8F8"; font.pixelSize: 14 }
                                    HoverHandler { id: editNoteHover }
                                    TapHandler {
                                        onTapped: { root.editNoteId = String(itemId || ""); root.editingNote = true; noteTitle.text = String(title || ""); noteContent.text = String(content || "") }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    function addTask() {
        var clean = taskTitle.text.trim()
        if (!clean.length) return
        var target = root.taskTargetGoogle ? "google" : "local"
        console.log("TASK_CREATE_CLICK target=" + target
                    + " workspace_connected=" + (coreBridge.googleWorkspaceStatus === "connected")
                    + " title_present=" + (clean.length > 0)
                    + " due_present=" + (taskDue.text.trim().length > 0))
        var ok = root.taskTargetGoogle
                 ? coreBridge.createGoogleTask(clean, taskDue.text.trim())
                 : coreBridge.createTask(clean, taskDue.text.trim())
        if (ok) {
            taskTitle.text = ""
            taskDue.text = ""
        }
    }
}
