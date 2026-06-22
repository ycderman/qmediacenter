"""Embedded libmpv player using QOpenGLWindow + createWindowContainer.

QOpenGLWindow gets Qt's dedicated render thread — paintGL() is never blocked
by the main event loop. This eliminates the mpv_render_context_render() stall
that plagues QOpenGLWidget-based implementations.
"""
import mpv
from PySide6.QtOpenGL import QOpenGLWindow
from PySide6.QtGui import QOpenGLContext
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal, QObject


def _get_proc_address(_ctx, name):
    glctx = QOpenGLContext.currentContext()
    if glctx is None:
        return 0
    name = name.decode("utf-8") if isinstance(name, bytes) else name
    return int(glctx.getProcAddress(name))


class _MpvSignals(QObject):
    """Signals must live on a QObject; QOpenGLWindow inherits QWindow, not QObject
    in the signal sense we need for cross-thread emit."""
    frame_ready    = Signal()
    duration_changed = Signal(float)
    position_changed = Signal(float)
    pause_changed    = Signal(bool)
    info_changed     = Signal(str)
    tracks_changed   = Signal(list)


class _MpvGLWindow(QOpenGLWindow):
    """Inner OpenGL window; paintGL runs in Qt's dedicated render thread."""

    def __init__(self, mpv_instance, signals: _MpvSignals):
        super().__init__()
        self._mpv = mpv_instance
        self._sig = signals
        self._render_ctx = None
        self._alive = True
        # frame_ready → update() wired after construction (same thread)

    def initializeGL(self):
        try:
            self._proc_addr_cb = mpv.MpvGlGetProcAddressFn(_get_proc_address)
            self._render_ctx = mpv.MpvRenderContext(
                self._mpv,
                "opengl",
                opengl_init_params={"get_proc_address": self._proc_addr_cb},
            )
            # mpv calls update_cb from its own thread; update() is thread-safe on QWindow
            self._render_ctx.update_cb = lambda: self._alive and self.update()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("MpvRenderContext init failed: %s", e)

    def paintGL(self):
        if self._render_ctx is None:
            return
        ratio = self.devicePixelRatio()
        w = int(self.width() * ratio)
        h = int(self.height() * ratio)
        self._render_ctx.render(
            flip_y=True,
            opengl_fbo={"w": w, "h": h, "fbo": 0},
        )

    def shutdown(self):
        self._alive = False
        if self._render_ctx is not None:
            try:
                self._render_ctx.free()
            except Exception:
                pass
            self._render_ctx = None


class MpvWidget(QWidget):
    """Public widget — embeds _MpvGLWindow via createWindowContainer."""

    duration_changed = Signal(float)
    position_changed = Signal(float)
    pause_changed    = Signal(bool)
    info_changed     = Signal(str)
    tracks_changed   = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._sig = _MpvSignals()
        self._hwdec = "?"
        self._vw = self._vh = 0
        self._alive = True

        self._mpv = mpv.MPV(
            vo="libmpv",
            hwdec="auto-safe",
            profile="fast",
            ytdl=False,
            osc=False,
            input_default_bindings=False,
            cache="yes",
            demuxer_max_bytes="200MiB",
            demuxer_max_back_bytes="100MiB",
            user_agent="QtIPTV/0.1",
        )

        self._mpv.observe_property("hwdec-current",  self._on_hwdec)
        self._mpv.observe_property("video-params/w", self._on_vparam)
        self._mpv.observe_property("video-params/h", self._on_vparam)
        self._mpv.observe_property("duration",    self._on_duration)
        self._mpv.observe_property("time-pos",    self._on_time_pos)
        self._mpv.observe_property("pause",       self._on_pause)
        self._mpv.observe_property("track-list",  self._on_tracks)

        self._gl_window = _MpvGLWindow(self._mpv, self._sig)
        container = QWidget.createWindowContainer(self._gl_window, self)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        # Forward signals from inner QObject to widget's public signals
        self._sig.duration_changed.connect(self.duration_changed)
        self._sig.position_changed.connect(self.position_changed)
        self._sig.pause_changed.connect(self.pause_changed)
        self._sig.info_changed.connect(self.info_changed)
        self._sig.tracks_changed.connect(self.tracks_changed)

    # ---- property callbacks (called from mpv thread) ------------------
    def _on_duration(self, _name, value):
        if self._alive and value is not None:
            self._sig.duration_changed.emit(float(value))

    def _on_time_pos(self, _name, value):
        if self._alive and value is not None:
            self._sig.position_changed.emit(float(value))

    def _on_pause(self, _name, value):
        if self._alive:
            self._sig.pause_changed.emit(bool(value))

    def _on_tracks(self, _name, value):
        if self._alive:
            self._sig.tracks_changed.emit(list(value) if value else [])

    def _on_hwdec(self, _name, value):
        if not self._alive:
            return
        self._hwdec = value or "software"
        self._emit_info()

    def _on_vparam(self, name, value):
        if not self._alive:
            return
        if value:
            if name == "video-params/w":
                self._vw = value
            elif name == "video-params/h":
                self._vh = value
        self._emit_info()

    def _emit_info(self):
        vparams = f"{self._vw}x{self._vh}" if self._vw and self._vh else ""
        parts = [p for p in (self._hwdec, vparams) if p and p != "?"]
        if parts:
            self._sig.info_changed.emit(" · ".join(parts))

    # ---- public API ---------------------------------------------------
    def play(self, url):
        self._mpv.play(url)
        self._mpv.pause = False

    def stop(self):
        try:
            self._mpv.command("stop")
        except Exception:
            pass

    def toggle_pause(self):
        self._mpv.pause = not self._mpv.pause

    def set_pause(self, paused: bool):
        self._mpv.pause = paused

    def seek(self, seconds, reference="absolute"):
        try:
            self._mpv.command("seek", seconds, reference)
        except Exception:
            pass

    def set_volume(self, volume: int):
        self._mpv.volume = max(0, min(150, volume))

    def set_audio(self, aid):
        try:
            self._mpv.aid = aid
        except Exception:
            pass

    def set_subtitle(self, sid):
        try:
            self._mpv.sid = sid
        except Exception:
            pass

    def shutdown(self):
        self._alive = False
        self._gl_window.shutdown()
        try:
            self._mpv.terminate()
        except Exception:
            pass
