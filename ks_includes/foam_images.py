import os
import re


def resolve_foam_image_path(manual_path, printer, screen, image_name):
    """Return {model}_{image_name} from the manual folder, or the shared image."""
    model_names = _printer_model_names(printer, screen)
    models, model_images = _available_model_images(manual_path, image_name)
    model = _match_model(model_names, models)

    if model:
        return model_images[model.casefold()]

    return os.path.join(manual_path, image_name)


def printer_matches_model(printer, screen, model):
    """Return whether the connected printer matches the requested model."""
    return _match_model(_printer_model_names(printer, screen), [model]) is not None


def _printer_model_names(printer, screen):
    model_names = set()
    if printer is not None:
        available_commands = getattr(printer, "available_commands", {})
        if isinstance(available_commands, dict):
            model_names.update(available_commands.keys())
        elif available_commands:
            model_names.update(available_commands)

        for method_name in ("get_gcode_macros", "get_hidden_gcode_macros"):
            method = getattr(printer, method_name, None)
            if callable(method):
                model_names.update(method())

    model_names.update(filter(None, (
        getattr(screen, "connected_printer", None),
        getattr(screen, "connecting_to_printer", None),
    )))
    return model_names


def _available_model_images(manual_path, image_name):
    models = []
    model_images = {}
    if not os.path.isdir(manual_path):
        return models, model_images

    suffix = f"_{image_name}".casefold()
    for entry in os.scandir(manual_path):
        if not entry.is_file() or not entry.name.casefold().endswith(suffix):
            continue
        model = entry.name[:-len(suffix)]
        model_key = model.casefold()
        if model_key not in model_images:
            models.append(model)
            model_images[model_key] = entry.path
    return models, model_images


def _match_model(model_names, models):
    normalized_names = {
        str(model_name).strip().casefold()
        for model_name in model_names
        if model_name is not None and str(model_name).strip()
    }
    for model in models:
        if model.casefold() in normalized_names:
            return model

    printer_keys = {
        key
        for model_name in model_names
        for key in _model_keys(model_name)
    }
    for model in models:
        if _model_keys(model) & printer_keys:
            return model

    prefix_matches = []
    for model in models:
        distance = _prefix_match_distance(_model_keys(model), printer_keys)
        if distance is not None:
            prefix_matches.append((distance, model.casefold(), model))
    return min(prefix_matches)[2] if prefix_matches else None


def _model_keys(model_name):
    model_key = re.sub(r"[^A-Z0-9]", "", str(model_name).upper())
    keys = {model_key} if model_key else set()
    if model_key.startswith("MD"):
        keys.add(model_key[2:])
    return keys


def _prefix_match_distance(model_keys, printer_keys):
    distances = []
    for model_key in model_keys:
        for printer_key in printer_keys:
            if len(model_key) < 4 or len(printer_key) < 4:
                continue
            if model_key.startswith(printer_key) or printer_key.startswith(model_key):
                distances.append(abs(len(model_key) - len(printer_key)))
    return min(distances) if distances else None
