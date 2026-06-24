"""QMediaCenter — Qt6/libmpv media center."""

try:
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("qmediacenter")
    except PackageNotFoundError:
        __version__ = "0.0.0+dev"
except ImportError:
    __version__ = "0.0.0+dev"
