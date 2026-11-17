"""Every screen's mapper has the same shape, so app.py can treat them alike: buttons(screen)
and hovering(screen) are methods (a property called by mistake, or a method left uncalled,
only shows in game), and reset_buttons() and update() exist."""

import importlib
import inspect
import pkgutil

import ttcontroller


def screen_mappers():
    for info in pkgutil.iter_modules(ttcontroller.__path__):
        if info.name in ("launcher", "settings_window", "__main__"):
            continue
        module = importlib.import_module(f"ttcontroller.{info.name}")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if name.endswith("Mapper") and cls.__module__ == module.__name__ and name != "OverworldMapper":
                yield cls


def test_there_are_mappers():
    assert len(list(screen_mappers())) >= 19


def test_every_mapper_has_the_same_interface():
    for cls in screen_mappers():
        for method in ("buttons", "reset_buttons", "update"):
            attr = inspect.getattr_static(cls, method, None)
            assert inspect.isfunction(attr), f"{cls.__name__}.{method} should be a method"
        params = list(inspect.signature(cls.buttons).parameters)
        assert params[:2] == ["self", "screen"], f"{cls.__name__}.buttons(screen)"
        hovering = inspect.getattr_static(cls, "hovering", None)
        if hovering is not None:
            assert inspect.isfunction(hovering), f"{cls.__name__}.hovering should be a method"
            assert list(inspect.signature(cls.hovering).parameters)[:2] == ["self", "screen"], cls.__name__
