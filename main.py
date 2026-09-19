"""AURA entry point — v0.7.0.15.6.2 Visual Fidelity RC."""
import logging
from logging.handlers import RotatingFileHandler
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from config.settings import settings
from security.redaction import RedactingFilter
from ui.main_window import MainWindow


def setup_logging():
    log_file = settings.LOG_DIR / "aura.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    redaction_filter = RedactingFilter()
    file_handler.addFilter(redaction_filter)
    console_handler.addFilter(redaction_filter)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[file_handler, console_handler],
    )


def main():
    setup_logging()
    logger = logging.getLogger("aura.main")
    logger.info("Demarrage de %s v%s...", settings.APP_NAME, settings.APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setApplicationVersion(settings.APP_VERSION)

    runtime = {"window": None}

    def bootstrap():
        try:
            # v0.7.0.11: there is no temporary splash. The definitive frameless shell is
            # visible immediately, already animated, but interaction remains
            # locked until MainWindow.startup_ready is emitted.
            window = MainWindow(startup_gate=True)
            runtime["window"] = window
            window.showMaximized()
            window.raise_()
            window.activateWindow()
            logger.info("Final Shell visible: Startup Gate verrouille")

            def on_ready():
                logger.info("Startup Gate ouvert: AURA interactive dans le meme shell")

            window.startup_ready.connect(on_ready)
            window.begin_startup()
        except Exception:
            logger.exception("Echec du demarrage securise d'AURA")
            app.quit()

    # Enter Qt first; then construct the single definitive application shell.
    QTimer.singleShot(0, bootstrap)
    exit_code = app.exec()
    logger.info("AURA fermee proprement.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
