from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Property

class EmptyListModel(QAbstractListModel):
    def rowCount(self, parent=QModelIndex()): return 0
    def data(self, index, role=Qt.DisplayRole): return None

class LocalTasksModel(QAbstractListModel):
    _roles = {Qt.UserRole + 1: b"itemId", Qt.UserRole + 2: b"title", Qt.UserRole + 3: b"dueDate", Qt.UserRole + 4: b"status"}
    def __init__(self, items=(), parent=None):
        super().__init__(parent); self._items = list(items)
    def roleNames(self): return self._roles
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self._items)
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)): return None
        item = self._items[index.row()]
        return item.get("task_id") if role == Qt.UserRole + 1 else item.get("title") if role == Qt.UserRole + 2 else item.get("due") if role == Qt.UserRole + 3 else ("DONE" if item.get("completed") else "OPEN") if role == Qt.UserRole + 4 else None
    def replace_items(self, items):
        self.beginResetModel(); self._items = list(items); self.endResetModel()
    @property
    def items(self): return list(self._items)

class LocalRemindersModel(QAbstractListModel):
    countChanged = Signal()
    _roles = {Qt.UserRole + 1: b"itemId", Qt.UserRole + 2: b"content", Qt.UserRole + 3: b"triggerAt"}
    def __init__(self, items=(), parent=None): super().__init__(parent); self._items = list(items)
    def roleNames(self): return self._roles
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self._items)
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)): return None
        item = self._items[index.row()]
        return item.get('reminder_id') if role == Qt.UserRole + 1 else item.get('content') if role == Qt.UserRole + 2 else item.get('trigger_at') if role == Qt.UserRole + 3 else None
    @Property(int, notify=countChanged)
    def count(self): return len(self._items)
    def replace_items(self, items):
        self.beginResetModel(); self._items = list(items); self.endResetModel(); self.countChanged.emit()
    @property
    def items(self): return list(self._items)

class LocalNotesModel(QAbstractListModel):
    countChanged=Signal(); _roles={Qt.UserRole+1:b"itemId",Qt.UserRole+2:b"title",Qt.UserRole+3:b"content",Qt.UserRole+4:b"createdAt",Qt.UserRole+5:b"updatedAt"}
    def __init__(self,items=(),parent=None): super().__init__(parent); self._items=list(items)
    def roleNames(self): return self._roles
    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self._items)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self._items): return None
        x=self._items[index.row()]; return x.get('note_id') if role==Qt.UserRole+1 else x.get('title') if role==Qt.UserRole+2 else x.get('content') if role==Qt.UserRole+3 else x.get('created_at') if role==Qt.UserRole+4 else x.get('updated_at') if role==Qt.UserRole+5 else None
    @Property(int,notify=countChanged)
    def count(self): return len(self._items)
    def replace_items(self,items): self.beginResetModel(); self._items=list(items); self.endResetModel(); self.countChanged.emit()
    @property
    def items(self): return list(self._items)
