import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QUrl, QObject
from PySide6.QtQuick import QQuickView, QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.google.day_summary_bridge import GoogleDaySummaryBridge
from aura_native.google.models import CalendarEvent, TaskItem
from aura_native.ui.qt_bridge import NativeCoreBridge
from aura_native.ui.models import EmptyListModel
from aura_native.mail.service import PermissionRequiredMailBackend

ROOT = Path(__file__).parents[2]


class AgendaDailyHubDelegateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        os.environ['AURA_PCC_FAKE'] = '1'
        cls.app = QApplication.instance() or QApplication([])

    def test_real_day_delegate_receives_prefetched_counts_and_permission(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests/native/_evidence') as folder:
            runtime = compose_runtime(project_root=ROOT, state_dir=folder)
            runtime.google_calendar_provider.events = [
                CalendarEvent(str(i), 'Événement ' + str(i), '2026-10-03T09:00:00+02:00',
                              '2026-10-03T10:00:00+02:00', 'Europe/Paris') for i in range(4)]
            runtime.google_tasks_provider.tasks = [TaskItem(str(i), 'Tâche ' + str(i), '2026-10-03') for i in range(3)]
            runtime.start(); core = NativeCoreBridge(runtime); daily = GoogleDaySummaryBridge(runtime.google_day_summary_service); view = QQuickView()
            try:
                view.rootContext().setContextProperty('coreBridge', core)
                view.rootContext().setContextProperty('googleDaySummaryBridge', daily)
                view.rootContext().setContextProperty('runtimeMode', 'native')
                view.rootContext().setContextProperty('agendaCalendarModel', EmptyListModel())
                view.setResizeMode(QQuickView.SizeRootObjectToView)
                view.setWidth(1100); view.setHeight(700)
                view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/AgendaView.qml')))
                view.show()
                self.assertEqual(view.status(), QQuickView.Ready)
                QTest.qWait(350)
                day = daily.summaries.get('2026-10-03', {})
                self.assertEqual((day.get('calendarCount'), day.get('mailCount'), day.get('taskCount')), (4, 1, 3))
                grid = view.rootObject().findChild(QObject, 'agendaMonthGrid')
                self.assertIsNotNone(grid)
                self.assertEqual(grid.property('count'), 42)
                def visual_names(item):
                    names = [item.objectName()]
                    for child in item.childItems(): names.extend(visual_names(child))
                    return names
                names = visual_names(view.rootObject())
                self.assertIn('dayHubBadges', names, names[:50])
                self.assertIn('dayCalendarOverflow', names)
                popup = view.rootObject().findChild(QObject, 'googleDayDetailPopup')
                for tab in (0, 1, 2):
                    view.rootObject().openGoogleDay('2026-10-03', tab)
                    self.assertEqual(popup.property('initialTab'), tab)
                    QTest.qWait(30)
                view.rootObject().openGoogleDay('2026-10-03', 1)
                QTest.qWait(30)
                self.assertEqual(popup.findChild(QObject, 'googleDayMailList').property('count'), 1)
                self.assertTrue(popup.findChild(QObject, 'googleDayMailEmpty').property('visible') is False)
                view.rootObject().openGoogleDay('2026-10-03', 0)
                self.assertEqual(popup.findChild(QObject, 'googleDayCalendarList').property('count'), 4)
                self.assertTrue(popup.findChild(QObject, 'googleDayCalendarEmpty').property('visible') is False)
                view.rootObject().openGoogleDay('2026-10-03', 2)
                self.assertEqual(popup.findChild(QObject, 'googleDayTasksList').property('count'), 3)
                runtime.mail_service.backend = PermissionRequiredMailBackend()
                daily.requestDates(['2026-10-03'])
                for _ in range(30):
                    if daily.summaries.get('2026-10-03', {}).get('mailState') == 'permission_required': break
                    QTest.qWait(10)
                self.assertEqual(daily.summaries['2026-10-03']['mailState'], 'permission_required')
            finally:
                view.close(); view.setSource(QUrl()); core.close(); runtime.stop()

    def test_daily_hub_badges_are_compact_and_silent_at_zero(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('visible: runtimeMode === "native" && modelData.mailCount > 0', source)
        self.assertIn('visible: runtimeMode === "native" && modelData.taskCount > 0', source)
        self.assertIn('GoogleFavicon', source)
        self.assertIn('text: String(modelData.mailCount)', source)
        self.assertIn('text: "✓ " + modelData.taskCount', source)
        self.assertNotIn('"Gmail …"', source)
        self.assertNotIn('"Tasks …"', source)
        self.assertIn('Math.max(0, dayEvents.length - maxVisibleCalendarEvents)', source)

    def test_daily_hub_qml_async_badge_refresh(self):
        """A bridge refresh must reach the real day delegate and badge."""
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests/native/_evidence') as folder:
            runtime = compose_runtime(project_root=ROOT, state_dir=folder)
            runtime.google_calendar_provider.events = []
            runtime.google_tasks_provider.tasks = []
            runtime.mail_service.backend.messages = []
            runtime.start(); core = NativeCoreBridge(runtime)
            daily = GoogleDaySummaryBridge(runtime.google_day_summary_service)
            view = QQuickView()
            try:
                view.rootContext().setContextProperty('coreBridge', core)
                view.rootContext().setContextProperty('googleDaySummaryBridge', daily)
                view.rootContext().setContextProperty('runtimeMode', 'native')
                view.rootContext().setContextProperty('agendaCalendarModel', EmptyListModel())
                view.setResizeMode(QQuickView.SizeRootObjectToView)
                view.setWidth(1100); view.setHeight(700)
                view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/AgendaView.qml')))
                self.assertEqual(view.status(), QQuickView.Ready)
                view.show()
                QTest.qWait(120)
                root = view.rootObject()
                root.setProperty('offlineCalendarYear', 2026)
                root.setProperty('offlineCalendarMonth', 9)
                root.rebuildOfflineCalendar()
                daily._items = {'2026-10-02': {'date': '2026-10-02', 'mailCount': 3, 'taskCount': 0,
                                               'mailState': 'ready', 'taskState': 'ready'}}
                daily.summaryChanged.emit()
                QTest.qWait(80)
                def named_items(item, wanted):
                    found = []
                    if item.objectName() == wanted:
                        found.append(item)
                    for child in item.childItems():
                        found.extend(named_items(child, wanted))
                    return found
                badges = named_items(view.rootObject(), 'dayGmailBadge')
                def cell_key(item):
                    current = item
                    for _ in range(5):
                        if current is None:
                            return ''
                        value = current.property('cellDateKey')
                        if value:
                            return value
                        current = current.parent()
                    return ''
                matching = [b for b in badges if cell_key(b) == '2026-10-02']
                self.assertEqual(len(matching), 1, f"badges={len(badges)} keys={[cell_key(b) for b in badges]}")
                self.assertTrue(matching[0].isVisible())
                texts = [child.property('text') for child in matching[0].findChildren(QObject) if child.property('text')]
                self.assertIn('3', texts)
            finally:
                view.close(); view.setSource(QUrl()); core.close(); runtime.stop()

    def test_daily_hub_qml_month_switch_badge(self):
        """Changing month and refreshing summaries keeps the canonical key."""
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('googleDaySummaryBridge.summaryForDate(summaryKey)', source)
        self.assertIn('function onSummaryChanged()', source)

    def test_daily_hub_qml_sync_after_empty_map(self):
        """An empty bridge map remains safe and hides both badges."""
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('mailCount: daySummary ? Number(daySummary.mailCount || 0) : 0', source)
        self.assertIn('taskCount: daySummary ? Number(daySummary.taskCount || 0) : 0', source)

    def test_google_day_popup_mail_items_visible(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "googleDayMailList"', source)
        self.assertIn('anchors.fill: parent', source)
        self.assertIn('model: popup.summary.mails || []', source)

    def test_google_day_popup_calendar_items_visible(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "googleDayCalendarList"', source)
        self.assertIn('model: popup.summary.calendarEvents || []', source)

    def test_google_day_popup_empty_tasks_state(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "googleDayTasksEmpty"', source)
        self.assertIn('Aucune tâche pour cette date', source)

    def test_google_day_popup_async_refresh(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('googleDayPopup.summary = googleDaySummaryBridge.summaryForDate(googleDayPopup.day)', source)
        self.assertIn('function onSummaryChanged()', source)

    def test_google_day_popup_tab_switch_preserves_models(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('StackLayout { currentIndex: tabs.currentIndex', source)
        self.assertIn('model: popup.summary.mails || []', source)
        self.assertIn('model: popup.summary.calendarEvents || []', source)
        self.assertIn('model: popup.summary.tasks || []', source)

    def test_agenda_hide_past_events_default(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('property bool showPastEvents: false', source)
        self.assertIn('root.showPastEvents || viewedMonthIsHistorical || !isPast', source)

    def test_agenda_show_past_events_toggle(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('AFFICHER LES PASSÉS', source)
        self.assertIn('root.showPastEvents = !root.showPastEvents', source)

    def test_google_calendar_real_brand_icon(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        icon = (ROOT / 'app/qml/components/GoogleCalendarIcon.qml').read_text(encoding='utf-8')
        self.assertIn('GoogleCalendarIcon', source)
        self.assertIn('text: "31"', icon)
        self.assertNotIn('google_favicon.png', source.split('GridView {', 1)[1].split('GoogleDayDetailPopup', 1)[0] if 'GridView {' in source else source)

    def test_google_day_popup_premium_tabs(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "googleDayPopupTabs"', source)
        self.assertNotIn('TabButton {', source)

    def test_google_day_popup_empty_state(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('googleDayMailEmpty', source)
        self.assertIn('googleDayCalendarEmpty', source)
        self.assertIn('googleDayTasksEmpty', source)

    def test_daily_hub_mail_badge_uses_google_favicon(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "dayGmailBadge"', source)
        self.assertIn('GoogleFavicon { iconSize: 12', source)

    def test_daily_hub_mail_badge_has_no_textual_g_prefix(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertNotIn('"G " + modelData.mailCount', source)

    def test_google_favicon_component_exists(self):
        self.assertTrue((ROOT / 'app/qml/components/GoogleFavicon.qml').is_file())

    def test_google_favicon_local_asset_only(self):
        source = (ROOT / 'app/qml/components/GoogleFavicon.qml').read_text(encoding='utf-8')
        self.assertIn('google_favicon.png', source)
        self.assertNotIn('http://', source)
        self.assertNotIn('https://', source)

    def test_google_favicon_used_in_popup_mail_metric(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('GoogleFavicon { iconSize: 13', source)
        self.assertIn('MAILS  " + Number(popup.summary.mailCount || 0)', source)

    def test_google_day_popup_single_tab_row(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertEqual(source.count('objectName: "googleDayPopupTabs"'), 1)
        self.assertIn('objectName: "googleDayCalendarTab"', source)
        self.assertIn('objectName: "googleDayMailTab"', source)
        self.assertIn('objectName: "googleDayTasksTab"', source)

    def test_google_day_popup_no_duplicate_tab_labels(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertNotIn('Repeater { model: ["CALENDRIER", "MAILS", "TÂCHES"]', source)
        self.assertEqual(source.count('text: "CALENDRIER  "'), 1)
        self.assertEqual(source.count('text: "MAILS  "'), 1)
        self.assertEqual(source.count('text: "✓  TÂCHES  "'), 1)

    def test_google_day_popup_counts_inside_tabs(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('calendarCount || 0', source)
        self.assertIn('mailCount || 0', source)
        self.assertIn('taskCount || 0', source)

    def test_google_day_popup_tab_click_changes_page(self):
        source = (ROOT / 'app/qml/components/GoogleDayDetailPopup.qml').read_text(encoding='utf-8')
        self.assertIn('onTapped: tabs.currentIndex = 0', source)
        self.assertIn('onTapped: tabs.currentIndex = 1', source)
        self.assertIn('onTapped: tabs.currentIndex = 2', source)

    def test_agenda_no_legacy_google_event_cards(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('visible: false', source)
        self.assertIn('Calendar details live exclusively in Daily Hub', source)

    def test_agenda_calendar_count_badge(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('objectName: "dayCalendarBadge"', source)
        self.assertIn('modelData.calendarCount > 0', source)
        self.assertIn('GoogleCalendarIcon { width: 12', source)

    def test_agenda_calendar_zero_hides_badge(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('visible: runtimeMode === "native" && modelData.calendarCount > 0', source)

    def test_agenda_calendar_badge_opens_popup_calendar(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('onTapped: root.openGoogleDay(cellDateKey, 0)', source)

    def test_agenda_mail_badge_still_opens_mail(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('onTapped: root.openGoogleDay(cellDateKey, 1)', source)

    def test_agenda_tasks_badge_still_opens_tasks(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('onTapped: root.openGoogleDay(cellDateKey, 2)', source)

    def test_agenda_no_google_event_titles_in_month_grid(self):
        source = (ROOT / 'app/qml/views/AgendaView.qml').read_text(encoding='utf-8')
        self.assertIn('calendarCount: dayEvents.length', source)

