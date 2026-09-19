"""
tasks.py
Gestion des taches d'AURA (section 12 du cahier des charges).
"""
import logging
from datetime import datetime

logger = logging.getLogger("aura.tasks")


class TaskManager:
    """CRUD sur la table `tasks`."""

    def __init__(self, db):
        self.db = db

    def create_task(self, title: str, description: str = None, priority: str = None,
                     category: str = None, due_date: str = None) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.conn.execute(
            "INSERT INTO tasks (title, description, priority, status, category, due_date, created_at) "
            "VALUES (?, ?, ?, 'TODO', ?, ?, ?)",
            (title, description, priority, category, due_date, now),
        )
        self.db.conn.commit()
        task_id = cursor.lastrowid
        logger.info(f"Tâche créée (id={task_id})")
        return task_id

    def list_tasks(self, status: str = None, limit: int = 20):
        if status:
            cursor = self.db.conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = self.db.conn.execute(
                "SELECT * FROM tasks WHERE status != 'CANCELLED' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_task(self, task_id: int):
        cursor = self.db.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_task_by_title(self, query: str):
        """Recherche la tâche non terminée la plus récente dont le titre contient `query`."""
        cursor = self.db.conn.execute(
            "SELECT * FROM tasks WHERE title LIKE ? AND status != 'DONE' "
            "ORDER BY created_at DESC LIMIT 1",
            (f"%{query}%",),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_status(self, task_id: int, status: str) -> bool:
        cursor = self.db.conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def complete_task(self, identifier: str):
        """Marque une tâche comme terminée, identifiée par son id ou un fragment de titre.
        Retourne la tâche mise à jour, ou None si introuvable."""
        identifier = identifier.strip()
        if identifier.isdigit():
            task = self.get_task(int(identifier))
        else:
            task = self.find_task_by_title(identifier)

        if task is None:
            return None

        self.set_status(task["id"], "DONE")
        task["status"] = "DONE"
        logger.info(f"Tâche terminée (id={task['id']})")
        return task
