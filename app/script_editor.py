"""Editor de script simple, similar a File > New Script en FreeMat."""
from PySide6.QtWidgets import QMainWindow, QPlainTextEdit, QToolBar, QFileDialog
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Signal

from highlighter import PythonHighlighter


class ScriptEditorWindow(QMainWindow):
    run_requested = Signal(str)

    def __init__(self, path: str | None = None):
        super().__init__()
        self.path = path
        self.setWindowTitle(path or "Untitled.m")
        self.resize(800, 600)

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.highlighter = PythonHighlighter(self.editor.document())
        self.setCentralWidget(self.editor)

        tb = QToolBar()
        self.addToolBar(tb)
        act_save = QAction("Guardar", self)
        act_save.triggered.connect(self.save)
        tb.addAction(act_save)
        act_run = QAction("▶ Ejecutar (F5)", self)
        act_run.setShortcut("F5")
        act_run.triggered.connect(self._run)
        tb.addAction(act_run)

        if path:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                self.editor.setPlainText(f.read())

    def _run(self):
        self.run_requested.emit(self.editor.toPlainText())

    def save(self):
        path = self.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar script", "Untitled.m",
                "Scripts FreeMat (*.m);;Python (*.py)"
            )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.path = path
            self.setWindowTitle(path)
