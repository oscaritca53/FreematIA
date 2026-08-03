"""Motor de ejecución: corre el código del usuario sin congelar la UI."""
import io
import sys
import traceback
import contextlib

from PySide6.QtCore import QThread, Signal

import numpy as np
import scipy
import sympy
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt


class ExecutionWorker(QThread):
    output_ready = Signal(str)
    error_ready = Signal(str)
    figures_ready = Signal(list)
    finished_run = Signal()

    def __init__(self, code: str, shared_namespace: dict):
        super().__init__()
        self.code = code
        self.namespace = shared_namespace

    def run(self):
        plt.close("all")
        buf_out = io.StringIO()

        # Entorno tipo "FreeMat": numpy, scipy, sympy y plot ya disponibles
        self.namespace.setdefault("np", np)
        self.namespace.setdefault("scipy", scipy)
        self.namespace.setdefault("sympy", sympy)
        self.namespace.setdefault("plt", plt)

        try:
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_out):
                exec(compile(self.code, "<freemat-ai>", "exec"), self.namespace)
            self.output_ready.emit(buf_out.getvalue())
        except Exception:
            self.output_ready.emit(buf_out.getvalue())
            self.error_ready.emit(traceback.format_exc())
        finally:
            fignums = plt.get_fignums()
            figures = [plt.figure(n) for n in fignums]
            self.figures_ready.emit(figures)
            self.finished_run.emit()
