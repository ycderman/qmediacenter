"""MPRIS2 DBus adapter — makes QMediaCenter visible to KDE Connect."""
import threading
import logging

log = logging.getLogger(__name__)

try:
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    log.warning("dbus-python/pygobject not found; MPRIS2 disabled")

MPRIS_IFACE  = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE  = "org.freedesktop.DBus.Properties"
BUS_NAME     = "org.mpris.MediaPlayer2.qmediacenter"
OBJECT_PATH  = "/org/mpris/MediaPlayer2"


class _MprisObject(dbus.service.Object):
    def __init__(self, bus, player_widget, initial_volume=100):
        dbus.service.Object.__init__(self, bus, OBJECT_PATH)
        self._player  = player_widget
        self._title   = ""
        self._art_url = ""
        self._paused  = True
        self._stopped = True
        self._dur     = 0.0
        self._pos     = 0.0
        self._vol     = max(0.0, min(1.0, initial_volume / 100.0))

        player_widget.pause_changed.connect(self._on_pause)
        player_widget.duration_changed.connect(self._on_duration)
        player_widget.position_changed.connect(self._on_position)

    # ---- called from MainWindow -----------------------------------------
    def on_play(self, title, art_url=""):
        self._title   = title or ""
        self._art_url = art_url or ""
        self._stopped = False
        self._paused  = False
        self._dur     = 0.0
        self._emit({
            "PlaybackStatus": dbus.String(self._status()),
            "Metadata":       self._metadata(),
        })

    def on_stop(self):
        self._stopped = True
        self._emit({"PlaybackStatus": dbus.String("Stopped")})

    def on_volume(self, volume_0_150):
        self._vol = max(0.0, min(1.5, volume_0_150 / 100.0))
        self._emit({"Volume": dbus.Double(self._vol)})

    # ---- mpv signal handlers -------------------------------------------
    def _on_pause(self, paused):
        self._paused = paused
        if not self._stopped:
            self._emit({"PlaybackStatus": dbus.String(self._status())})

    def _on_duration(self, dur):
        self._dur = dur
        if not self._stopped:
            self._emit({"Metadata": self._metadata()})

    def _on_position(self, pos):
        self._pos = pos

    # ---- helpers --------------------------------------------------------
    def _status(self):
        if self._stopped:
            return "Stopped"
        return "Paused" if self._paused else "Playing"

    def _metadata(self):
        meta = {
            "mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/track/1"),
            "xesam:title":   dbus.String(self._title),
            "mpris:length":  dbus.Int64(int(self._dur * 1_000_000)),
        }
        if self._art_url:
            url = self._art_url
            if url.startswith("/"):
                url = "file://" + url
            meta["mpris:artUrl"] = dbus.String(url)
        return dbus.Dictionary(meta, signature="sv")

    def _emit(self, changed):
        self.PropertiesChanged(PLAYER_IFACE, changed, dbus.Array([], signature="s"))

    # ---- org.freedesktop.DBus.Properties --------------------------------
    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, iface, name):
        return self.GetAll(iface).get(name, dbus.String(""))

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        if iface == MPRIS_IFACE:
            return {
                "CanQuit":             dbus.Boolean(False),
                "CanRaise":            dbus.Boolean(False),
                "HasTrackList":        dbus.Boolean(False),
                "Identity":            dbus.String("QMediaCenter"),
                "DesktopEntry":        dbus.String("io.github.ycderman.qmediacenter"),
                "SupportedUriSchemes": dbus.Array([], signature="s"),
                "SupportedMimeTypes":  dbus.Array([], signature="s"),
            }
        if iface == PLAYER_IFACE:
            return {
                "PlaybackStatus": dbus.String(self._status()),
                "LoopStatus":     dbus.String("None"),
                "Rate":           dbus.Double(1.0),
                "Shuffle":        dbus.Boolean(False),
                "Metadata":       self._metadata(),
                "Volume":         dbus.Double(self._vol),
                "Position":       dbus.Int64(int(self._pos * 1_000_000)),
                "MinimumRate":    dbus.Double(1.0),
                "MaximumRate":    dbus.Double(1.0),
                "CanGoNext":      dbus.Boolean(False),
                "CanGoPrevious":  dbus.Boolean(False),
                "CanPlay":        dbus.Boolean(True),
                "CanPause":       dbus.Boolean(True),
                "CanSeek":        dbus.Boolean(True),
                "CanControl":     dbus.Boolean(True),
            }
        return {}

    @dbus.service.method(PROPS_IFACE, in_signature="ssv")
    def Set(self, iface, name, value):
        if iface == PLAYER_IFACE and name == "Volume":
            v = float(value)
            self._vol = max(0.0, min(1.5, v))
            self._player.set_volume(int(v * 100))

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, iface, changed, invalidated):
        pass

    # ---- org.mpris.MediaPlayer2 -----------------------------------------
    @dbus.service.method(MPRIS_IFACE)
    def Raise(self): pass

    @dbus.service.method(MPRIS_IFACE)
    def Quit(self): pass

    # ---- org.mpris.MediaPlayer2.Player ----------------------------------
    @dbus.service.method(PLAYER_IFACE)
    def Next(self): pass

    @dbus.service.method(PLAYER_IFACE)
    def Previous(self): pass

    @dbus.service.method(PLAYER_IFACE)
    def Pause(self):
        self._player.set_pause(True)

    @dbus.service.method(PLAYER_IFACE)
    def PlayPause(self):
        self._player.toggle_pause()

    @dbus.service.method(PLAYER_IFACE)
    def Stop(self):
        self._player.stop()

    @dbus.service.method(PLAYER_IFACE)
    def Play(self):
        self._player.set_pause(False)

    @dbus.service.method(PLAYER_IFACE, in_signature="x")
    def Seek(self, offset_us):
        self._player.seek(int(offset_us) / 1_000_000, "relative")

    @dbus.service.method(PLAYER_IFACE, in_signature="ox")
    def SetPosition(self, _track_id, pos_us):
        self._player.seek(int(pos_us) / 1_000_000, "absolute")

    @dbus.service.method(PLAYER_IFACE, in_signature="s")
    def OpenUri(self, uri): pass

    @dbus.service.signal(PLAYER_IFACE, signature="x")
    def Seeked(self, position_us): pass


class MprisAdapter:
    """Create once in main(), wire to MainWindow._play() / _on_back()."""

    def __init__(self, player_widget, initial_volume=100):
        self._obj = None
        if not _AVAILABLE:
            return
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            bus.request_name(BUS_NAME)
            self._obj = _MprisObject(bus, player_widget, initial_volume)
            loop = GLib.MainLoop()
            threading.Thread(target=loop.run, daemon=True, name="mpris-glib").start()
            log.info("MPRIS2 registered as %s", BUS_NAME)
        except Exception as e:
            log.warning("MPRIS2 init failed: %s", e)

    def on_play(self, title, art_url=""):
        if self._obj:
            self._obj.on_play(title, art_url)

    def on_stop(self):
        if self._obj:
            self._obj.on_stop()

    def on_volume_change(self, volume_0_150):
        if self._obj:
            self._obj.on_volume(volume_0_150)
