def launch_gui() -> int:
    from .app import launch_gui as _launch_gui
    return _launch_gui()


__all__ = ["launch_gui"]
