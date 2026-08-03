"""Motor de ejecución: corre código Python sobre un namespace compartido
(equivalente al 'workspace' de FreeMat) y captura stdout/stderr."""
import io
import contextlib
import traceback

import numpy as np
import scipy
import sympy
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt


def make_namespace() -> dict:
    ns = {}
    ns["np"] = np
    ns["scipy"] = scipy
    ns["sympy"] = sympy
    ns["plt"] = plt
    return ns


def run_code(code: str, namespace: dict):
    """Ejecuta código en el namespace dado. Devuelve (salida, error_o_None, figuras)."""
    buf = io.StringIO()
    error = None
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            compiled = compile(code, "<freemat-ai>", "single" if "\n" not in code.strip() else "exec")
            exec(compiled, namespace)
    except Exception:
        error = traceback.format_exc()
    figures = [plt.figure(n) for n in plt.get_fignums()]
    return buf.getvalue(), error, figures


VISIBLE_TYPES_ONLY_SKIP = {"np", "scipy", "sympy", "plt", "__builtins__"}


def visible_variables(namespace: dict):
    """Filtra el namespace para mostrar solo variables 'de usuario' (como el panel Variables)."""
    out = []
    for name, value in namespace.items():
        if name in VISIBLE_TYPES_ONLY_SKIP or name.startswith("__"):
            continue
        if callable(value) and not isinstance(value, (int, float, str, bool)):
            continue
        cls = type(value).__name__
        try:
            val_repr = repr(value)
        except Exception:
            val_repr = "<repr error>"
        if len(val_repr) > 60:
            val_repr = val_repr[:57] + "..."
        out.append((name, cls, val_repr))
    return sorted(out)
