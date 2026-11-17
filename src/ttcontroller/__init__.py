"""Controller support for Toontown Rewritten."""

__version__ = "0.9.0b1"  # also in pyproject.toml


def display_version(v: str = __version__) -> str:
    """For people: "0.9.0b1" is "0.9 beta", "1.0.0" is "1.0", "1.2.3" stays."""
    import re
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?", v)
    if not m:
        return v
    major, minor, patch, pre, _ = m.groups()
    number = f"{major}.{minor}" + (f".{patch}" if patch != "0" else "")
    return number + {"a": " alpha", "b": " beta", "rc": " release candidate", None: ""}[pre]
