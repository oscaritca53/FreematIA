"""
Gestor de Ollama para IA local. No puede "empaquetar" un modelo de varios
GB dentro de un único .exe (ver README para la explicación completa), pero
sí puede automatizar todo lo demás: detectar si Ollama está instalado,
arrancar su servidor si no está corriendo, y descargar el modelo elegido
la primera vez -- sin que el usuario tenga que abrir una terminal.
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal


def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def is_server_running(base_url: str) -> bool:
    try:
        urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def start_server():
    """Lanza 'ollama serve' en segundo plano, sin ventana de consola en Windows."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(["ollama", "serve"], **kwargs)


def list_models(base_url: str) -> list[str]:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def is_model_pulled(base_url: str, model: str) -> bool:
    names = list_models(base_url)
    base_name = model.split(":")[0]
    return any(n == model or n.split(":")[0] == base_name for n in names)


def pull_model(model: str, progress_callback=None) -> bool:
    """Ejecuta 'ollama pull <model>' y reporta cada línea de progreso."""
    try:
        proc = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except FileNotFoundError:
        if progress_callback:
            progress_callback("No se encontró el comando 'ollama'.")
        return False

    for line in proc.stdout:
        if progress_callback:
            progress_callback(line.strip())
    proc.wait()
    return proc.returncode == 0


def ensure_ready(base_url: str, model: str, progress_callback=None):
    """Se asegura de que Ollama esté instalado, corriendo, y con el modelo
    descargado. Devuelve (ok: bool, mensaje: str)."""
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    if not is_ollama_installed():
        return False, (
            "Ollama no está instalado. Descárgalo de "
            "https://ollama.com/download e instálalo, luego vuelve a intentar."
        )

    if not is_server_running(base_url):
        report("Iniciando el servidor de Ollama...")
        start_server()
        for _ in range(20):
            time.sleep(0.5)
            if is_server_running(base_url):
                break
        else:
            return False, "No se pudo iniciar el servidor de Ollama (tardó demasiado)."
        report("Servidor iniciado.")

    if is_model_pulled(base_url, model):
        report(f"El modelo '{model}' ya está disponible.")
        return True, "Listo."

    report(f"Descargando el modelo '{model}' (puede tardar varios minutos)...")
    ok = pull_model(model, progress_callback=report)
    if not ok:
        return False, f"No se pudo descargar el modelo '{model}'."
    report("Modelo descargado.")
    return True, "Listo."


class OllamaSetupWorker(QThread):
    """Corre ensure_ready() en segundo plano y emite el progreso en vivo."""
    progress = Signal(str)
    finished_setup = Signal(bool, str)

    def __init__(self, base_url: str, model: str):
        super().__init__()
        self.base_url = base_url
        self.model = model

    def run(self):
        ok, msg = ensure_ready(self.base_url, self.model, progress_callback=self.progress.emit)
        self.finished_setup.emit(ok, msg)
