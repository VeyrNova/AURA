import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import "../components"

Item {
    id: root
    property bool lightMode: false
    // AURA_GOOGLE_CALENDAR_QT_FIX19
    // AURA_GOOGLE_ACCOUNT_CONNECT_FIX20
    // AURA_GOOGLE_BIDIRECTIONAL_FIX21
    // AURA_CALENDAR_SELECTABLE_EDIT_FIX24
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX26
    // AURA_PRODUCTIVITY_LAYOUT_GOOGLE_FIX28
    // AURA_GOOGLE_FAVICON_FIX29
    // AURA_PRODUCTIVITY_PREMIUM_VISUAL_FIX27
    // AURA_PRODUCTIVITY_PREMIUM_DRAWERS_FIX25
    property bool createOnGoogle: true
    property var offlineCalendarModel: []
    property int offlineCalendarYear: new Date().getFullYear()
    property int offlineCalendarMonth: new Date().getMonth()
    property bool calendarSyncing: false
    property bool showPastEvents: false
    readonly property int maxVisibleCalendarEvents: 2
    GoogleDayDetailPopup { id: googleDayPopup; parent: root; anchors.centerIn: parent; z: 50 }
    function openGoogleDay(dayKey, tabIndex) {
        if (!googleDaySummaryBridge) return
        googleDayPopup.day = dayKey
        googleDayPopup.initialTab = tabIndex
        googleDayPopup.summary = googleDaySummaryBridge.summaryForDate(dayKey)
        googleDayPopup.open()
    }
    function requestDaySummaries() {
        if (runtimeMode !== "native" || !googleDaySummaryBridge) return
        var keys = []
        for (var i = 0; i < offlineCalendarModel.length; i++) {
            var row = offlineCalendarModel[i]
            keys.push(row.year + "-" + String(row.month + 1).padStart(2, "0") + "-" + String(row.dayNumber).padStart(2, "0"))
        }
        googleDaySummaryBridge.requestDates(keys)
    }
    Connections {
        target: runtimeMode === "native" ? googleDaySummaryBridge : null
        function onSummaryChanged() {
            root.rebuildOfflineCalendar()
            if (googleDayPopup.visible) googleDayPopup.summary = googleDaySummaryBridge.summaryForDate(googleDayPopup.day)
        }
    }

    Connections {
        target: coreBridge
        function onGoogleCalendarEventsChanged() {
            console.log("B44_QML_EVENTS_CHANGED count=" + coreBridge.googleCalendarEvents.length)
            root.rebuildOfflineCalendar()
        }
        function onMessagesChanged() { if (coreBridge.googleCalendarStatus !== "loading") root.calendarSyncing = false }
    }

    function rebuildOfflineCalendar() {
        var first = new Date(offlineCalendarYear, offlineCalendarMonth, 1)
        var offset = (first.getDay() + 6) % 7
        var count = new Date(offlineCalendarYear, offlineCalendarMonth + 1, 0).getDate()
        var previous = new Date(offlineCalendarYear, offlineCalendarMonth, 0).getDate()
        var now = new Date(), rows = []
        var eventsReceived = (coreBridge.googleCalendarEvents || []).length
        var eventsMapped = 0, eventsUnmapped = 0, cellsWithEvents = 0, labelsWith = 0, labelsWithout = 0
        var dateKeys = []
        for (var i = 0; i < 42; i++) {
            var index = i - offset + 1, year = offlineCalendarYear, month = offlineCalendarMonth
            var day = index, inMonth = true
            if (index < 1) { day = previous + index; month--; inMonth = false }
            else if (index > count) { day = index - count; month++; inMonth = false }
            if (month < 0) { month = 11; year-- }
            if (month > 11) { month = 0; year++ }
            var dayEvents = []
            var events = coreBridge.googleCalendarEvents || []
            for (var e = 0; e < events.length; e++) {
                var eventDay = String(events[e].dateKey || events[e].start || "").slice(0, 10)
                var cellDate = year + "-" + String(month + 1).padStart(2, "0") + "-" + String(day).padStart(2, "0")
                var currentDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
                var viewedMonthIsHistorical = (year < now.getFullYear()) || (year === now.getFullYear() && month < now.getMonth())
                var eventEnd = new Date(String(events[e].end || events[e].start || ""))
                var isPast = !isNaN(eventEnd.getTime()) && eventEnd < currentDay
                if (eventDay === cellDate && (root.showPastEvents || viewedMonthIsHistorical || !isPast)) dayEvents.push({source: "google", label: String(events[e].title || "Sans titre"), external_id: String(events[e].id || ""), start_at: String(events[e].start || ""), end_at: String(events[e].end || "")})
                if (dateKeys.indexOf(eventDay) < 0) dateKeys.push(eventDay)
            }
            eventsMapped += dayEvents.length; if (dayEvents.length) cellsWithEvents++
            for (var p = 0; p < dayEvents.length; p++) { if (String(dayEvents[p].label || "").length) labelsWith++; else labelsWithout++ }
            var summaryKey = year + "-" + String(month + 1).padStart(2, "0") + "-" + String(day).padStart(2, "0")
            // Read through the bridge contract instead of indexing the Python
            // QVariantMap directly.  The bridge signal is the sole refresh
            // trigger, and this method keeps the date-key normalization in
            // one place for QML.
            var daySummary = (typeof googleDaySummaryBridge !== "undefined" && googleDaySummaryBridge)
                             ? googleDaySummaryBridge.summaryForDate(summaryKey)
                             : null
            rows.push({date: new Date(year, month, day), day: day, month: month, year: year,
                dayNumber: day, inMonth: inMonth, isCurrentMonth: inMonth,
                isToday: year === now.getFullYear() && month === now.getMonth() && day === now.getDate(),
                eventCount: dayEvents.length, calendarCount: dayEvents.length, firstEventPayload: dayEvents[0] || {}, secondEventPayload: dayEvents[1] || {}, thirdEventPayload: dayEvents[2] || {},
                overflowCount: Math.max(0, dayEvents.length - maxVisibleCalendarEvents), mailCount: daySummary ? Number(daySummary.mailCount || 0) : 0,
                taskCount: daySummary ? Number(daySummary.taskCount || 0) : 0,
                mailState: daySummary ? String(daySummary.mailState || "unknown") : "unknown",
                taskState: daySummary ? String(daySummary.taskState || "unknown") : "unknown"})
        }
        offlineCalendarModel = rows
        eventsUnmapped = Math.max(0, eventsReceived - eventsMapped)
        console.log("B44_QML_CALENDAR_REBUILD events=" + eventsReceived + " mapped=" + eventsMapped + " unmapped=" + eventsUnmapped + " cells_with_events=" + cellsWithEvents + " payloads_with_label=" + labelsWith + " payloads_without_label=" + labelsWithout)
    }
    function offlineMonthLabel() {
        var names = ["JANVIER","FÉVRIER","MARS","AVRIL","MAI","JUIN","JUILLET","AOÛT","SEPTEMBRE","OCTOBRE","NOVEMBRE","DÉCEMBRE"]
        return names[offlineCalendarMonth] + " " + offlineCalendarYear
    }
    function previousOfflineMonth() { if (offlineCalendarMonth === 0) { offlineCalendarMonth = 11; offlineCalendarYear-- } else offlineCalendarMonth--; rebuildOfflineCalendar(); requestDaySummaries() }
    function nextOfflineMonth() { if (offlineCalendarMonth === 11) { offlineCalendarMonth = 0; offlineCalendarYear++ } else offlineCalendarMonth++; rebuildOfflineCalendar(); requestDaySummaries() }
    function todayOfflineMonth() { var now = new Date(); offlineCalendarYear = now.getFullYear(); offlineCalendarMonth = now.getMonth(); rebuildOfflineCalendar(); requestDaySummaries() }

    property string editGoogleEventId: ""
    property string editGoogleEventTitle: ""
    property string editGoogleEventStart: ""
    property string editGoogleEventEnd: ""
    property string editGoogleEventDescription: ""

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

    function beginGoogleEventEdit(payload) {
        if (!payload || String(payload.source || "") !== "google")
            return

        var id = String(payload.external_id || "")
        if (!id.length)
            return

        editGoogleEventId = id
        editGoogleEventTitle = String(payload.title || "")
        editGoogleEventStart = calendarInput(payload.start_at)
        editGoogleEventEnd = calendarInput(payload.end_at)
        editGoogleEventDescription = String(
            payload.description || ""
        )
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

    FileDialog {
        id: googleOAuthDialog
        title: "Sélectionner le fichier OAuth Google"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Fichier OAuth Google (*.json)"]
        onAccepted: coreBridge.connectGoogle(selectedFile.toString())
    }

    function refreshGoogle() {
        calendarSyncing = true
        var first = offlineCalendarModel.length ? offlineCalendarModel[0].date : new Date(offlineCalendarYear, offlineCalendarMonth, 1)
        var last = offlineCalendarModel.length ? offlineCalendarModel[offlineCalendarModel.length - 1].date : new Date(offlineCalendarYear, offlineCalendarMonth + 1, 0)
        var end = new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1)
        coreBridge.refreshGoogleCalendar(first.toISOString(), end.toISOString())
        rebuildOfflineCalendar()
        requestDaySummaries()
    }
    function connectGoogleWorkspace() {
        if (coreBridge.googleOAuthClientStatus.configured) coreBridge.startGoogleWorkspaceOAuth()
        else googleOAuthDialog.open()
    }

    Component.onCompleted: {
        rebuildOfflineCalendar()
        requestDaySummaries()
        coreBridge.agendaToday()
        refreshGoogle()
    }
    onVisibleChanged: if (visible) refreshGoogle()

    ContextDrawer {
        id: drawer
        lightMode: root.lightMode
        titleText: "AGENDA · AURA + GOOGLE"
        subtitleText: coreBridge.googleCalendarStatus
        drawerWidth: 1000
        accentColor: "#74EFFF"
        premiumSurface: true
        headerHeight: 88
        titlePixelSize: 17
        subtitlePixelSize: 10

        Rectangle {
            parent: drawer.headerActions
            width: 154; height: 44; radius: 13
            color: refreshHover.hovered ? "#7A0E4056" : "#58081726"
            border.width: 1; border.color: refreshHover.hovered ? "#6574EFFF" : "#3974DDEA"
            objectName: "agendaSynchronize"
            Text { anchors.centerIn: parent; text: root.calendarSyncing ? "SYNCHRONISATION..." : "SYNCHRONISER"; color: "#8DE8F5"; font.pixelSize: 8; font.weight: Font.DemiBold }
            HoverHandler { id: refreshHover }
            TapHandler { onTapped: { console.log("B44_AGENDA_SYNC_CLICK"); root.refreshGoogle() } }
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
            anchors.margins: 18
            spacing: 12

            Rectangle {
                width: parent.width; height: 64; radius: 14
                color: "#8A071D2B"; border.width: 1
                border.color: coreBridge.googleWorkspaceStatus === "connected" ? "#2D72DDEC" : "#23556E7D"
                Row {
                    anchors.fill: parent; anchors.leftMargin: 15; anchors.rightMargin: 14
                    Column {
                        width: parent.width - 118
                        anchors.verticalCenter: parent.verticalCenter; spacing: 3
                        Text { text: "AGENDA · AURA + GOOGLE CALENDAR"; color: "#D8F9FF"; font.pixelSize: 10; font.weight: Font.DemiBold }
                        Text { text: coreBridge.googleCalendarStatus; color: "#5D8092"; font.pixelSize: 8 }
                    }
                    Row {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                        Text { anchors.verticalCenter: parent.verticalCenter; text: coreBridge.googleCalendarCount + " GOOGLE"; color: "#83E6F5"; font.pixelSize: 8; font.weight: Font.DemiBold }
                        Rectangle {
                            width: 126; height: 30; radius: 9
                            color: pastHover.hovered ? "#243D6170" : "transparent"
                            border.width: 1; border.color: root.showPastEvents ? "#3E8FA8B8" : "#25536D7D"
                            Text { anchors.centerIn: parent; text: root.showPastEvents ? "MASQUER LES PASSÉS" : "AFFICHER LES PASSÉS"; color: "#83E6F5"; font.pixelSize: 7; font.weight: Font.DemiBold }
                            HoverHandler { id: pastHover }
                            TapHandler { onTapped: { root.showPastEvents = !root.showPastEvents; root.rebuildOfflineCalendar() } }
                        }
                    }
                }
            }

            Rectangle {
                visible: coreBridge.googleCalendarStatus !== "connected"
                width: parent.width
                height: visible ? 32 : 0
                radius: 8
                color: agendaGoogleConnectHover.hovered ? "#235FE7F5" : "#5C0D2636"
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
                HoverHandler { id: agendaGoogleConnectHover }
                TapHandler {
                    enabled: !coreBridge.googleConnecting
                    onTapped: root.connectGoogleWorkspace()
                }
            }

            Rectangle {
                width: parent.width; height: 62; radius: 14
                color: "#76061322"; border.width: 1; border.color: "#3374DDEB"
                Row {
                    anchors.fill: parent; anchors.margins: 8; spacing: 8
                    Rectangle {
                        width: 44; height: 38; radius: 11
                        color: prevHover.hovered ? "#1D74EFFF" : "transparent"
                        border.width: 1; border.color: "#2C70DDEA"
                        Text { anchors.centerIn: parent; text: "‹"; color: "#AEEFFF"; font.pixelSize: 20; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
                        HoverHandler { id: prevHover }
                        TapHandler { onTapped: { previousOfflineMonth(); coreBridge.agendaPreviousMonth(); root.refreshGoogle() } }
                    }
                    Rectangle {
                        width: 128; height: 38; radius: 11
                        color: todayHover.hovered ? "#1A74EFFF" : "transparent"
                        border.width: 1; border.color: "#286EDCEB"
                        Text { anchors.centerIn: parent; text: "AUJOURD’HUI"; color: "#98E8F4"; font.pixelSize: 8 }
                        HoverHandler { id: todayHover }
                        TapHandler { onTapped: { todayOfflineMonth(); coreBridge.agendaToday(); root.refreshGoogle() } }
                    }
                    Text {
                        width: Math.max(80, parent.width - 260)
                        anchors.verticalCenter: parent.verticalCenter
                        horizontalAlignment: Text.AlignHCenter
                        text: offlineMonthLabel()
                        color: "#D8F5FF"; font.pixelSize: 16; font.weight: Font.DemiBold; font.letterSpacing: 1.4
                    }
                    Rectangle {
                        width: 44; height: 38; radius: 11
                        color: nextHover.hovered ? "#1D74EFFF" : "transparent"
                        border.width: 1; border.color: "#2C70DDEA"
                        Text { anchors.centerIn: parent; text: "›"; color: "#AEEFFF"; font.pixelSize: 20; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
                        HoverHandler { id: nextHover }
                        TapHandler { onTapped: { nextOfflineMonth(); coreBridge.agendaNextMonth(); root.refreshGoogle() } }
                    }
                }
            }

            Grid {
                width: parent.width; columns: 7; spacing: 4
                Repeater {
                    model: ["LUN","MAR","MER","JEU","VEN","SAM","DIM"]
                    delegate: Text {
                        width: (parent.width - 24) / 7; height: 30
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        text: modelData; color: "#5B7D8F"; font.pixelSize: 9; font.letterSpacing: 0.9
                    }
                }
            }

            GridView {
                id: monthGrid
                objectName: "agendaMonthGrid"
                width: parent.width
                height: {
                    var editing = root.editGoogleEventId.length > 0
                    var maxHeight = editing ? 360 : 470
                    var reserved = editing ? 520 : 370
                    return Math.max(
                        220,
                        Math.min(maxHeight, parent.height - reserved)
                    )
                }
                cellWidth: width / 7
                cellHeight: height / 6
                model: offlineCalendarModel.length ? offlineCalendarModel : agendaCalendarModel
                clip: true; interactive: false

                delegate: Item {
                    width: monthGrid.cellWidth; height: monthGrid.cellHeight
                    property string cellDateKey: String(modelData.year) + "-" + String(modelData.month + 1).padStart(2, "0") + "-" + String(modelData.dayNumber).padStart(2, "0")
                    Rectangle {
                        id: dayCard
                        anchors.fill: parent; anchors.margins: 4; radius: 12
                        color: modelData.isToday ? "#301B5260" : "#3A071722"
                        border.width: 1
                        border.color: modelData.isToday ? "#6474EFFF" : "#2864A6B8"
                        opacity: modelData.inMonth ? 1 : 0.42
                        Text {
                            anchors.left: parent.left; anchors.top: parent.top
                            anchors.leftMargin: 10; anchors.topMargin: 8
                            text: String(modelData.dayNumber); color: modelData.inMonth ? "#C9F5FF" : "#66818E"; font.pixelSize: 10
                        }
                        Column {
                            id: eventsColumn
                            // Calendar details live exclusively in Daily Hub.
                            // Keep payloads for editing compatibility, but do
                            // not render legacy title chips in the month grid.
                            visible: false
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top; anchors.topMargin: 24
                            anchors.leftMargin: 6; anchors.rightMargin: 6
                            spacing: 3
                            z: 2
                            clip: false
                            Repeater {
                                model: modelData.eventCount > 0 ? [
                                    modelData.firstEventPayload,
                                    modelData.secondEventPayload
                                ] : []

                                delegate: Rectangle {
                                    id: eventDelegate
                                    property var eventPayload: modelData
                                    property bool isGoogle:
                                        String(eventPayload.source || "")
                                        === "google"
                                    property bool selected:
                                        isGoogle
                                        && String(
                                            eventPayload.external_id || ""
                                        ) === root.editGoogleEventId

                                    visible:
                                        String(
                                            eventPayload.label || ""
                                        ).length > 0

                                    x: 0
                                    width: Math.max(1, eventsColumn.width)
                                    height: visible ? 26 : 0
                                    z: 3
                                    radius: 10

                                    color: selected
                                           ? "#4F176075"
                                           : (
                                               isGoogle
                                               ? (
                                                   eventHover.hovered
                                                   ? "#3A1E7187"
                                                   : "#2B27849B"
                                               )
                                               : "#2B9155E1"
                                           )

                                    border.width:
                                        selected || eventHover.hovered
                                        ? 1
                                        : 0
                                    border.color:
                                        selected
                                        ? "#6DD7F2FF"
                                        : "#3676DDEA"

                                    GoogleCalendarIcon {
                                        id: eventGoogleIcon
                                        visible: isGoogle
                                        anchors.left: parent.left
                                        anchors.leftMargin: 5
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 14
                                        height: 14
                                    }

                                    Text {
                                        anchors.left: isGoogle ? eventGoogleIcon.right : parent.left
                                        anchors.right: isGoogle ? eventPencil.left : parent.right
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        anchors.leftMargin: isGoogle ? 4 : 5
                                        anchors.rightMargin: 3
                                        verticalAlignment: Text.AlignVCenter
                                        elide: Text.ElideRight
                                        text: (eventPayload.allDay || !eventPayload.timeLabel)
                                              ? String(eventPayload.label || eventPayload.title || "")
                                              : String(eventPayload.timeLabel) + "  " + String(eventPayload.label || eventPayload.title || "")
                                        color: isGoogle ? "#A7EFF8" : "#CDB4FF"
                                        font.pixelSize: 8
                                    }

                                    PencilIcon {
                                        id: eventPencil
                                        visible: isGoogle
                                        anchors.right: parent.right
                                        anchors.rightMargin: 3
                                        anchors.verticalCenter:
                                            parent.verticalCenter
                                        width: 16
                                        height: 16
                                        iconColor:
                                            selected
                                            ? "#D9FBFF"
                                            : "#79DDEB"
                                        detailColor: "#E9FDFF"
                                    }

                                    HoverHandler {
                                        id: eventHover
                                        enabled: isGoogle
                                        cursorShape:
                                            Qt.PointingHandCursor
                                    }

                                    TapHandler {
                                        enabled: isGoogle
                                        onTapped:
                                            root.beginGoogleEventEdit(
                                                eventPayload
                                            )
                                    }

                                    ToolTip.visible:
                                        isGoogle
                                        && eventHover.hovered
                                    ToolTip.text:
                                        "Modifier cet événement"
                                    ToolTip.delay: 350
                                }
                            }
                            Text { objectName: "dayCalendarOverflow"; visible: modelData.overflowCount > 0; text: "+" + modelData.overflowCount + " événements"; color: "#A8CDE0"; font.pixelSize: 8; TapHandler { onTapped: root.openGoogleDay(cellDateKey, 0) } }
                        }
                        Row { objectName: "dayHubBadges"; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.leftMargin: 6; anchors.rightMargin: 6; anchors.bottomMargin: 6; spacing: 4
                            Rectangle { objectName: "dayCalendarBadge"; visible: runtimeMode === "native" && modelData.calendarCount > 0; width: 34; height: 18; radius: 7; color: "#32214F68"; border.width: 1; border.color: "#4B7CA8C0"
                                Row { anchors.centerIn: parent; spacing: 3
                                    GoogleCalendarIcon { width: 12; height: 12; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: String(modelData.calendarCount); color: "#AEEFFF"; font.pixelSize: 8; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                                }
                                TapHandler { onTapped: root.openGoogleDay(cellDateKey, 0) }
                            }
                            Rectangle { objectName: "dayGmailBadge"; visible: runtimeMode === "native" && modelData.mailCount > 0; width: 34; height: 18; radius: 7; color: "#321D6173"; border.width: 1; border.color: "#4B9CB0C0"
                                Row { anchors.centerIn: parent; spacing: 3
                                    GoogleFavicon { iconSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: String(modelData.mailCount); color: "#AEEFFF"; font.pixelSize: 8; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                                }
                                TapHandler { onTapped: root.openGoogleDay(cellDateKey, 1) }
                                ToolTip.visible: gmailHover.hovered; ToolTip.text: "Voir les mails du jour"; HoverHandler { id: gmailHover }
                            }
                            Rectangle { objectName: "dayTasksBadge"; visible: runtimeMode === "native" && modelData.taskCount > 0; width: 34; height: 18; radius: 7; color: "#322D6F56"; border.width: 1; border.color: "#4B72C28D"
                                Text { anchors.centerIn: parent; text: "✓ " + modelData.taskCount; color: "#C8FFE0"; font.pixelSize: 8; font.weight: Font.DemiBold }
                                TapHandler { onTapped: root.openGoogleDay(cellDateKey, 2) }
                                ToolTip.visible: tasksHover.hovered; ToolTip.text: "Voir les tâches du jour"; HoverHandler { id: tasksHover }
                            }
                        }
                    }
                }
            }

            Rectangle {
                visible: root.editGoogleEventId.length > 0
                width: parent.width
                height: visible ? 176 : 0
                radius: 14
                color: "#A10A1B29"
                border.width: 1
                border.color: "#4A74EFFF"

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Row {
                        width: parent.width
                        height: 18

                        Text {
                            width: parent.width - 90
                            anchors.verticalCenter:
                                parent.verticalCenter
                            text:
                                "MODIFIER L’ÉVÉNEMENT GOOGLE"
                            color: "#90EAF5"
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                        }

                        Text {
                            width: 90
                            anchors.verticalCenter:
                                parent.verticalCenter
                            horizontalAlignment:
                                Text.AlignRight
                            text: "Sélection calendrier"
                            color: "#507486"
                            font.pixelSize: 8
                        }
                    }

                    TextField {
                        width: parent.width
                        height: 34
                        text: root.editGoogleEventTitle
                        placeholderText: "Titre"
                        color: "#D7F7FF"
                        placeholderTextColor: "#607F91"
                        font.pixelSize: 9
                        leftPadding: 8
                        rightPadding: 8
                        onTextChanged:
                            root.editGoogleEventTitle = text
                        background: Rectangle {
                            radius: 10
                            color: "#A604101A"
                            border.width: 1
                            border.color: "#286ED9EA"
                        }
                    }

                    Row {
                        width: parent.width
                        height: 34
                        spacing: 6

                        TextField {
                            width: (parent.width - 6) / 2
                            height: 34
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
                                radius: 10
                                color: "#A604101A"
                                border.width: 1
                                border.color: "#286ED9EA"
                            }
                        }

                        TextField {
                            width: (parent.width - 6) / 2
                            height: 34
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
                                radius: 10
                                color: "#A604101A"
                                border.width: 1
                                border.color: "#286ED9EA"
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        height: 34
                        spacing: 6

                        TextField {
                            width: parent.width - 172
                            height: 34
                            text:
                                root.editGoogleEventDescription
                            placeholderText: "Description"
                            color: "#D7F7FF"
                            placeholderTextColor: "#607F91"
                            font.pixelSize: 9
                            leftPadding: 8
                            rightPadding: 8
                            onTextChanged:
                                root.editGoogleEventDescription = text
                            background: Rectangle {
                                radius: 10
                                color: "#A604101A"
                                border.width: 1
                                border.color: "#286ED9EA"
                            }
                        }

                        Rectangle {
                            width: 108
                            height: 36
                            radius: 10
                            color:
                                saveCalendarEditHover.hovered
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
                                id: saveCalendarEditHover
                            }

                            TapHandler {
                                onTapped:
                                    root.saveGoogleEventEdit()
                            }
                        }

                        Rectangle {
                            width: 108
                            height: 36
                            radius: 10
                            color:
                                cancelCalendarEditHover.hovered
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
                                id: cancelCalendarEditHover
                            }

                            TapHandler {
                                onTapped:
                                    root.cancelGoogleEventEdit()
                            }
                        }
                    }
                }
            }

            Rectangle { width: parent.width; height: 1; color: "#1468D3E6" }

            Column {
                width: parent.width
                height: 118
                spacing: 7

                Row {
                    width: parent.width; height: 36; spacing: 10
                    Text { width: 74; anchors.verticalCenter: parent.verticalCenter; text: "CRÉER DANS"; color: "#5E8296"; font.pixelSize: 8; font.letterSpacing: 0.8 }
                    Rectangle {
                        objectName: "agendaCreateTargetLocal"
                        width: 126; height: 34; radius: 10
                        color: !root.createOnGoogle ? "#4B237497" : "transparent"
                        border.width: 1; border.color: !root.createOnGoogle ? "#2B74DCEC" : "#1B527889"
                        Text { anchors.centerIn: parent; text: "AURA RAPPEL"; color: !root.createOnGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                        TapHandler { onTapped: root.createOnGoogle = false }
                    }
                    Rectangle {
                        objectName: "agendaCreateTargetGoogle"
                        width: 154; height: 34; radius: 10
                        enabled: coreBridge.googleWorkspaceStatus === "connected"
                        opacity: enabled ? 1 : 0.45
                        color: root.createOnGoogle ? "#4B237497" : "transparent"
                        border.width: 1; border.color: root.createOnGoogle ? "#2B74DCEC" : "#1B527889"
                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            GoogleCalendarIcon { width: 14; height: 14 }
                            Text { text: "GOOGLE CALENDAR"; color: root.createOnGoogle ? "#B9F2FF" : "#648596"; font.pixelSize: 8 }
                        }
                        TapHandler { enabled: parent.enabled; onTapped: root.createOnGoogle = true }
                    }
                }

                Row {
                    width: parent.width; height: 44; spacing: 10
                    TextField {
                        id: reminderText
                        width: parent.width - 306; height: 42
                        placeholderText: root.createOnGoogle ? "Nouvel événement Google…" : "Nouveau rappel AURA…"
                        color: "#C7F3FF"; placeholderTextColor: "#607F91"
                        background: Rectangle { radius: 8; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                    }
                    TextField {
                        id: reminderWhen
                        width: 190; height: 42
                        placeholderText: "YYYY-MM-DDTHH:MM"
                        color: "#C7F3FF"; placeholderTextColor: "#607F91"
                        background: Rectangle { radius: 8; color: "#98030D16"; border.width: 1; border.color: "#236BD8EA" }
                    }
                    Rectangle {
                        width: 88; height: 42; radius: 11
                        color: addHover.hovered ? "#2674EFFF" : "#5A0D2432"
                        border.width: 1; border.color: "#3270DDEA"
                        Text { anchors.centerIn: parent; text: "AJOUTER"; color: "#AEEFFF"; font.pixelSize: 8 }
                        HoverHandler { id: addHover }
                        TapHandler {
                            onTapped: {
                                var ok = root.createOnGoogle
                                         ? coreBridge.createGoogleEvent(reminderText.text, reminderWhen.text, "", "")
                                         : coreBridge.createReminder(reminderText.text, reminderWhen.text)
                                if (ok) {
                                    reminderText.text = ""; reminderWhen.text = ""
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}






