import json
import re
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QLabel, QMainWindow,
    QMessageBox, QVBoxLayout, QWidget
)
import vlc


CONFIG = Path(__file__).with_name("cameras.json")

PAGE_SIZE = 4               # maximum number of cameras displayed at once
FALLBACK_RETRY_MS = 3000    # time between retries when there is no signal
PRIMARY_RECOVERY_MS = 30000  # time to try switching back to the primary stream


class CameraWidget(QFrame):
    _error_signal = Signal()
    _end_signal = Signal()
    _playing_signal = Signal()

    def __init__(self, camera, instance, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.instance = instance
        self.player = instance.media_player_new()
        self.fallback_attempted = False
        self.current_subtype = 0

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background: #111;
                border: 1px solid #333;
            }
        """)

        self.video = QFrame()
        self.video.setStyleSheet("background: black;")
        self.video.setAttribute(Qt.WA_NativeWindow, True)

        self.title = QLabel(camera.get("name", "Camera"))
        self.title.setStyleSheet(
            "color: white; background: rgba(0,0,0,180); padding: 5px;"
        )
        self.title.setFont(QFont("Arial", 11, QFont.Bold))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video, 1)
        layout.addWidget(self.title, 0)

        self.status = QLabel("Connecting...")
        self.status.setStyleSheet(
            "color: white; background: #222; padding: 4px;"
        )
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status, 0)

        self.video.installEventFilter(self)
        self.title.installEventFilter(self)
        self.status.installEventFilter(self)

        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self.play)

        self.primary_recovery_timer = QTimer(self)
        self.primary_recovery_timer.setSingleShot(True)
        self.primary_recovery_timer.timeout.connect(self._attempt_primary_recovery)

        self._error_signal.connect(self._try_fallback)
        self._end_signal.connect(self._try_fallback)
        self._playing_signal.connect(self._handle_playing_ok)

        self.player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEncounteredError, self._on_error
        )
        self.player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEndReached, self._on_end
        )
        self.player.event_manager().event_attach(
            vlc.EventType.MediaPlayerPlaying, self._on_playing
        )

    def _native_id(self):
        return int(self.video.winId())

    def _url_for_subtype(self, subtype):
        url = self.camera["url"]
        if "{subtype}" in url:
            return url.replace("{subtype}", str(subtype))
        if "subtype=" in url:
            return re.sub(r"subtype=\d+", f"subtype={subtype}", url)
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}subtype={subtype}"

    def play(self):
        if self.player is None:
            return
        self.status.setText(f"Connecting (subtype={self.current_subtype})...")

        old_media = self.player.get_media()

        media = self.instance.media_new(self._url_for_subtype(self.current_subtype))
        media.add_option(":rtsp-tcp")
        media.add_option(":network-caching=1000")
        self.player.set_media(media)

        if old_media is not None:
            old_media.release()

        if sys.platform.startswith("darwin"):
            self.player.set_nsobject(self._native_id())
        elif sys.platform.startswith("win"):
            self.player.set_hwnd(self._native_id())
        else:
            self.player.set_xwindow(self._native_id())

        self.player.play()

        QTimer.singleShot(6000, self.check_playing)

    def check_playing(self):
        if self.player is None:
            return
        state = self.player.get_state()
        if state in (
            vlc.State.Error,
            vlc.State.Ended,
            vlc.State.Stopped,
        ):
            self._try_fallback()

    def _on_error(self, event):
        self._error_signal.emit()

    def _on_end(self, event):
        self._end_signal.emit()

    def _on_playing(self, event):
        self._playing_signal.emit()

    def _handle_playing_ok(self):
        if self.player is None:
            return
        if self.current_subtype == 0:
            self.status.setText("Live")
            self.primary_recovery_timer.stop()
        else:
            self.status.setText("Live (secondary stream)")
            if not self.primary_recovery_timer.isActive():
                self.primary_recovery_timer.start(PRIMARY_RECOVERY_MS)

    def _try_fallback(self):
        if self.player is None:
            return
        if self.current_subtype == 0 and not self.fallback_attempted:
            self.fallback_attempted = True
            self.current_subtype = 1
            self.status.setText("Primary stream failed; trying secondary...")
            self.retry_timer.start(500)
        else:
            self.status.setText("No signal — retrying...")
            self.retry_timer.start(FALLBACK_RETRY_MS)

    def _attempt_primary_recovery(self):
        if self.player is None:
            return
        if self.current_subtype != 0:
            self.current_subtype = 0
            self.fallback_attempted = False
            self.status.setText("Trying to switch back to the primary stream...")
            self.play()

    def shutdown(self):
        self.retry_timer.stop()
        self.primary_recovery_timer.stop()

        player = self.player
        self.player = None 

        def _do_shutdown():
            try:
                player.stop()
            except Exception:
                pass
            media = player.get_media()
            if media is not None:
                try:
                    media.release()
                except Exception:
                    pass
            try:
                player.release()
            except Exception:
                pass

        threading.Thread(target=_do_shutdown, daemon=True).start()

    def _handle_double_click(self):
        window = self.window()
        if hasattr(window, "toggle_fullscreen_camera"):
            window.toggle_fullscreen_camera(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonDblClick:
            self._handle_double_click()
            return True
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event):
        self._handle_double_click()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, cameras):
        super().__init__()
        self.setWindowTitle("IP Camera Viewer")
        self.resize(1400, 900)
        self.setStyleSheet("background: #000;")

        self.instance = vlc.Instance(
            "--no-video-title-show",
            "--quiet"
        )

        self.all_cameras = cameras
        self.pages = [
            cameras[i:i + PAGE_SIZE]
            for i in range(0, len(cameras), PAGE_SIZE)
        ] or [[]]
        self.current_page = 0

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(4)
        for i in range(2):
            self.grid.setRowStretch(i, 1)
            self.grid.setColumnStretch(i, 1)

        self.page_label = QLabel("")
        self.page_label.setStyleSheet(
            "color: white; background: rgba(0,0,0,150); padding: 4px;"
        )
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setFixedHeight(24)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.container, 1)
        outer.addWidget(self.page_label, 0)

        central = QWidget()
        central.setLayout(outer)
        self.setCentralWidget(central)

        self.camera_widgets = []
        self.fullscreen_widget = None
        self._original_positions = {}
        self._started = False

        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(self.exit_camera_fullscreen)

        next_page = QShortcut(QKeySequence(Qt.Key_Right), self)
        next_page.activated.connect(self.next_page)
        prev_page = QShortcut(QKeySequence(Qt.Key_Left), self)
        prev_page.activated.connect(self.prev_page)

        self._build_page(self.current_page)

    def _clear_grid(self):
        for widget in self.camera_widgets:
            widget.shutdown()
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self.camera_widgets = []

    def _positions_for(self, count):
        if count == 1:
            return [(0, 0, 2, 2)]
        if count == 2:
            return [(0, 0, 2, 1), (0, 1, 2, 1)]
        if count == 3:
            return [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 2)]
        return [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]

    def _build_page(self, page_index):
        self._clear_grid()
        self.fullscreen_widget = None
        self._original_positions = {}

        cameras = self.pages[page_index]
        positions = self._positions_for(len(cameras)) if cameras else []

        for camera, (row, col, rowspan, colspan) in zip(cameras, positions):
            widget = CameraWidget(camera, self.instance)
            self.camera_widgets.append(widget)
            self.grid.addWidget(widget, row, col, rowspan, colspan)
            self._original_positions[widget] = (row, col, rowspan, colspan)

        if len(self.pages) > 1:
            self.page_label.setText(
                f"Page {page_index + 1}/{len(self.pages)}  (← / → to navigate)"
            )
            self.page_label.setVisible(True)
        else:
            self.page_label.setVisible(False)

        if self._started:
            for widget in self.camera_widgets:
                widget.play()

    def next_page(self):
        if len(self.pages) <= 1 or self.fullscreen_widget is not None:
            return
        self.current_page = (self.current_page + 1) % len(self.pages)
        self._build_page(self.current_page)

    def prev_page(self):
        if len(self.pages) <= 1 or self.fullscreen_widget is not None:
            return
        self.current_page = (self.current_page - 1) % len(self.pages)
        self._build_page(self.current_page)

    def toggle_fullscreen_camera(self, widget):
        if self.fullscreen_widget is widget:
            self.exit_camera_fullscreen()
            return

        self.fullscreen_widget = widget
        for w in self.camera_widgets:
            if w is widget:
                self.grid.addWidget(w, 0, 0, 2, 2)
                w.setVisible(True)
            else:
                w.setVisible(False)
        self.page_label.setVisible(False)

    def exit_camera_fullscreen(self):
        if self.fullscreen_widget is None:
            return

        widget = self.fullscreen_widget
        row, col, rowspan, colspan = self._original_positions[widget]
        self.grid.addWidget(widget, row, col, rowspan, colspan)

        for w in self.camera_widgets:
            w.setVisible(True)
        if len(self.pages) > 1:
            self.page_label.setVisible(True)

        self.fullscreen_widget = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self._started:
            self._started = True
            for widget in self.camera_widgets:
                widget.play()

    def closeEvent(self, event):
        self._clear_grid()
        super().closeEvent(event)


def load_config():
    if not CONFIG.exists():
        raise FileNotFoundError(f"File not found: {CONFIG}")

    with CONFIG.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cameras = data.get("cameras", [])
    if not cameras:
        raise ValueError("cameras.json must contain at least 1 camera.")

    return cameras


def main():
    app = QApplication(sys.argv)

    try:
        cameras = load_config()
    except Exception as e:
        QMessageBox.critical(None, "Configuration Error", str(e))
        return 1

    window = MainWindow(cameras)
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())