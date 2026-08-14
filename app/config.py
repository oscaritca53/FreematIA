"""Configuración persistente de la app. Se guarda en un archivo local para
no depender de variables de entorno (poco práctico en un .exe empaquetado)."""
import os
import json

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".freemat_ai_studio")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_api_key() -> str | None:
    cfg = load_config()
    key = cfg.get("api_key")
    if key:
        return key
    # compatibilidad hacia atrás: si alguien sí configuró la variable de entorno
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def set_api_key(key: str):
    cfg = load_config()
    cfg["api_key"] = key.strip()
    save_config(cfg)
