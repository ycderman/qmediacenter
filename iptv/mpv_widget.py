"""Embedded libmpv player rendered into a Qt OpenGL widget."""
import mpv
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QOpenGLContext
from PySide6.QtCore import Signal


def _get_proc_address(_ctx, name):
    glctx = QOpenGLContext.currentContext()
    if glctx is None:
        return 0
    name = name.decode("utf-8") if isinstance(name, bytes) else name
    return int(glctx.getProcAddress(name))


class MpvWidget(QOpenGLWidget):
    _frame_ready = Signal()

    duration_changed = Signal(float)
    position_changed = Signal(float)
    pause_changed    = Signal(bool)
    info_changed     = Signal(str)
    tracks_changed   = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mpv = mpv.MPV(
            vo="libmpv",
            hwdec="vaapi",
            hwdec_codecs="all",
            input_default_bindings=False,
            # Fast profile + explicit GPU-light settings for 4K
            profile="fast",
            video_sync="audio",
            interpolation="no",
            framedrop="decoder",
            scale="bilinear",
            cscale="bilinear",
            dscale="bilinear",
            dither_depth="no",
            tone_mapping="clip",
            hdr_compute_peak="no",
            # Intel UHD 620 GLES needs rgba8 FBO; without it mpv enters dumb mode
            fbo_format="rgba8",
            # Decoder threading
            vd_lavc_threads=0,
            demuxer_thread="yes",
            # Default cache for non-live content (overridden per play() call)
            cache="yes",
            cache_pause=False,
            demuxer_max_bytes="512MiB",
            demuxer_max_back_bytes="128MiB",
            cache_secs=60,
            user_agent="QtIPTV/0.1",
            log_handler=self._mpv_log,
            loglevel="warn",
        )
        self._alive = True
        self._hwdec = "?"
        self._vw = self._vh = 0
        self._render_ctx = None
        self._frame_ready.connect(self.update)

        self._mpv.observe_property("hwdec-current",  self._on_hwdec)
        self._mpv.observe_property("video-params/w", self._on_vparam)
        self._mpv.observe_property("video-params/h", self._on_vparam)
        self._mpv.observe_property("duration",       self._on_duration)
        self._mpv.observe_property("time-pos",       self._on_time_pos)
        self._mpv.observe_property("pause",          self._on_pause)
        self._mpv.observe_property("track-list",     self._on_tracks)

    @staticmethod
    def _mpv_log(level, component, message):
        import logging
        logging.getLogger(f"mpv.{component}").warning("[%s] %s", level, message.rstrip())

    def initializeGL(self):
        try:
            self._proc_addr_cb = mpv.MpvGlGetProcAddressFn(_get_proc_address)
            self._render_ctx = mpv.MpvRenderContext(
                self._mpv,
                "opengl",
                opengl_init_params={"get_proc_address": self._proc_addr_cb},
            )
            self._render_ctx.update_cb = lambda: self._alive and self._frame_ready.emit()
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

    def _on_duration(self, _name, value):
        if self._alive and value is not None:
            self.duration_changed.emit(float(value))

    def _on_time_pos(self, _name, value):
        if self._alive and value is not None:
            self.position_changed.emit(float(value))

    def _on_pause(self, _name, value):
        if self._alive:
            self.pause_changed.emit(bool(value))

    def _on_tracks(self, _name, value):
        if self._alive:
            self.tracks_changed.emit(list(value) if value else [])

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
            self.info_changed.emit(" · ".join(parts))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            self.seek(20 if delta > 0 else -20, "relative")
        event.accept()

    def play(self, url, live=False):
        if live:
            self._mpv["demuxer-max-bytes"]      = "64MiB"
            self._mpv["demuxer-max-back-bytes"] = "8MiB"
            self._mpv["cache-secs"]             = 10
        else:
            self._mpv["demuxer-max-bytes"]      = "512MiB"
            self._mpv["demuxer-max-back-bytes"] = "128MiB"
            self._mpv["cache-secs"]             = 60
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
        if self._render_ctx is not None:
            try:
                self.makeCurrent()
                self._render_ctx.free()
            except Exception:
                pass
            self._render_ctx = None
        try:
            self._mpv.terminate()
        except Exception:
            pass
