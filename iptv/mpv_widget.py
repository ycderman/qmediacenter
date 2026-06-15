"""Embedded libmpv player rendered into a Qt OpenGL widget.

Uses libmpv's render API (OpenGL) so it works on both Wayland and X11 —
unlike `--wid` embedding which only works under X11. mpv handles every
codec (HEVC, AC3/E-AC3, DTS, ...) with VAAPI hardware decoding.
"""
import mpv
from OpenGL import GL
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QOpenGLContext
from PySide6.QtCore import Qt, Signal


def _get_proc_address(_ctx, name):
    glctx = QOpenGLContext.currentContext()
    if glctx is None:
        return 0
    name = name.decode("utf-8") if isinstance(name, bytes) else name
    return int(glctx.getProcAddress(name))


class MpvWidget(QOpenGLWidget):
    """A QOpenGLWidget that draws an mpv video surface."""

    # Emitted (from the GUI thread) whenever mpv signals a new frame is ready.
    _frame_ready = Signal()

    duration_changed = Signal(float)
    position_changed = Signal(float)
    pause_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mpv = mpv.MPV(
            vo="libmpv",
            hwdec="auto-safe",            # VAAPI (UHD 620) when safe; never breaks playback
            ytdl=False,
            osc=False,
            input_default_bindings=False,
            cache="yes",
            demuxer_max_bytes="200MiB",   # bigger buffer for high-bitrate 4K streams
            demuxer_max_back_bytes="100MiB",
            user_agent="QtIPTV/0.1",
        )
        # log which decoder actually engaged (helps diagnose slow 4K)
        self._mpv.observe_property("hwdec-current", self._on_hwdec)
        self._render_ctx = None
        self._frame_ready.connect(self.update)

        # observers -> Qt signals (marshalled via the queued _frame_ready style)
        self._mpv.observe_property("duration", self._on_duration)
        self._mpv.observe_property("time-pos", self._on_time_pos)
        self._mpv.observe_property("pause", self._on_pause)

    # ---- GL lifecycle -------------------------------------------------
    def initializeGL(self):
        try:
            # Must be a ctypes CFUNCTYPE instance; keep a ref so it isn't GC'd.
            self._proc_addr_cb = mpv.MpvGlGetProcAddressFn(_get_proc_address)
            self._render_ctx = mpv.MpvRenderContext(
                self._mpv,
                "opengl",
                opengl_init_params={"get_proc_address": self._proc_addr_cb},
            )
            # mpv calls this from a non-GUI thread; just ask Qt to repaint.
            self._render_ctx.update_cb = lambda: self._frame_ready.emit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("MpvRenderContext init failed: %s", e)
            self._render_ctx = None

    def paintGL(self):
        if self._render_ctx is None:
            return
        ratio = self.devicePixelRatioF()
        w = int(self.width() * ratio)
        h = int(self.height() * ratio)
        fbo = self.defaultFramebufferObject()
        self._render_ctx.render(
            flip_y=True,
            opengl_fbo={"w": w, "h": h, "fbo": fbo},
        )

    # ---- property callbacks ------------------------------------------
    def _on_duration(self, _name, value):
        if value is not None:
            self.duration_changed.emit(float(value))

    def _on_time_pos(self, _name, value):
        if value is not None:
            self.position_changed.emit(float(value))

    def _on_pause(self, _name, value):
        self.pause_changed.emit(bool(value))

    def _on_hwdec(self, _name, value):
        import logging
        logging.getLogger(__name__).info("hwdec-current = %s", value)

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
            self._mpv.seek(seconds, reference)
        except Exception:
            pass

    def set_volume(self, volume: int):
        self._mpv.volume = max(0, min(150, volume))

    def shutdown(self):
        if self._render_ctx is not None:
            try:
                self.makeCurrent()
            except Exception:
                pass
            self._render_ctx.free()
            self._render_ctx = None
        try:
            self._mpv.terminate()
        except Exception:
            pass
