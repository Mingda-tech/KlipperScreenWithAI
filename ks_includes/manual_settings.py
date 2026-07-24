import math


ZOFFSET_LIMIT = 10.0


def normalize_zoffset(value):
    """Return a safe Z offset as a float, or None when it is unknown/invalid."""
    if value is None or isinstance(value, bool):
        return None
    try:
        zoffset = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(zoffset) or abs(zoffset) >= ZOFFSET_LIMIT:
        return None
    return zoffset


def zoffset_is_adjusted(value):
    zoffset = normalize_zoffset(value)
    return zoffset is not None and abs(zoffset) > 0.001


def build_zoffset_restore_command(value, homed):
    zoffset = normalize_zoffset(value)
    if zoffset is None:
        return None
    return f"SET_GCODE_OFFSET Z={zoffset} MOVE={1 if homed else 0}"


def ensure_manual_settings(manual_settings, tools, right_zoffset=0.0, reset=False):
    """Ensure every tool has settings while keeping zero distinct from unknown."""
    if reset:
        manual_settings.clear()

    configured_right_zoffset = normalize_zoffset(right_zoffset)
    if configured_right_zoffset is None:
        configured_right_zoffset = 0.0

    for index, extruder in enumerate(tools):
        if index == 0:
            default_zoffset = 0.0
        elif extruder == "extruder1":
            default_zoffset = configured_right_zoffset
        else:
            # Do not override an unfamiliar tool until its actual offset is observed.
            default_zoffset = None

        settings = manual_settings.setdefault(extruder, {})
        settings.setdefault("extruder_temp", 0.0)
        settings.setdefault("speedfactor", 0.0)
        settings.setdefault("extrudefactor", 0.0)
        settings.setdefault("zoffset_manually_set", False)
        if "zoffset" not in settings or normalize_zoffset(settings["zoffset"]) is None:
            settings["zoffset"] = default_zoffset


def get_manual_zoffset(manual_settings, extruder):
    settings = manual_settings.get(extruder)
    if not settings:
        return None
    return normalize_zoffset(settings.get("zoffset"))


def store_manual_zoffset(manual_settings, extruder, value, manually_set=False):
    zoffset = normalize_zoffset(value)
    if zoffset is None or extruder not in manual_settings:
        return False
    settings = manual_settings[extruder]
    if settings.get("zoffset_manually_set", False) and not manually_set:
        return False
    settings["zoffset"] = zoffset
    if manually_set:
        settings["zoffset_manually_set"] = True
    return True
