"""
FreeMat AI Studio
Entorno visual de cálculo matemático con motor Python (numpy/scipy/sympy)
y asistente de 'vibecoding' integrado (Claude API).
"""
import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QSplitter, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QToolBar, QLabel,
    QFileDialog, QDockWidget, QLineEdit, QMessageBox, QTextEdit
)
from PySide6.QtGui import QFont, QAction, QIcon
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from highlighter import PythonHighlighter
from executor import ExecutionWorker
from ai_assistant import generate_code, AIAssistantError


MONO_FONT = "Consolas" if sys.platform == "win32" else "Monospace"


class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        font = QFont(MONO_FONT, 12)
        self.setFont(font)
        self.setStyleSheet("background:#1e1e1e; color:#d4d4d4; border:none;")
        self.setPlaceholderText(
            "# Escribe tu código aquí (numpy=np, scipy, sympy, matplotlib=plt)\n"
            "x = np.linspace(0, 10, 200)\n"
            "y = np.sin(x)\n"
            "plt.plot(x, y)\n"
            "plt.title('Ejemplo')\n"
        )
        self.highlighter = PythonHighlighter(self.document())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreeMat AI Studio")
        self.resize(1300, 850)
        self.shared_namespace = {}
        self.worker = None
        self.current_file = None

        self._build_ui()
        self._build_toolbar()
        self._build_ai_dock()

    # ---------- UI ----------
    def _build_ui(self):
        splitter = QSplitter(Qt.Vertical)

        self.editor = CodeEditor()

        self.tabs = QTabWidget()
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background:#0c0c0c; color:#dddddd;")
        self.console.setFont(QFont(MONO_FONT, 11))
        self.tabs.addTab(self.console, "Consola")

        self.plot_tabs = QTabWidget()
        self.tabs.addTab(self.plot_tabs, "Gráficas")

        splitter.addWidget(self.editor)
        splitter.addWidget(self.tabs)
        splitter.setSizes([500, 350])

        self.setCentralWidget(splitter)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_new = QAction("Nuevo", self)
        act_new.triggered.connect(self.new_file)
        tb.addAction(act_new)

        act_open = QAction("Abrir", self)
        act_open.triggered.connect(self.open_file)
        tb.addAction(act_open)

        act_save = QAction("Guardar", self)
        act_save.triggered.connect(self.save_file)
        tb.addAction(act_save)

        tb.addSeparator()

        act_run = QAction("▶ Ejecutar (F5)", self)
        act_run.setShortcut("F5")
        act_run.triggered.connect(self.run_code)
        tb.addAction(act_run)

        tb.addSeparator()
        act_ai = QAction("✨ Asistente IA", self)
        act_ai.triggered.connect(lambda: self.ai_dock.setVisible(not self.ai_dock.isVisible()))
        tb.addAction(act_ai)

    def _build_ai_dock(self):
        self.ai_dock = QDockWidget("Vibecoding / Asistente IA", self)
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Describe lo que quieres calcular o pega un prompt:"))
        self.ai_prompt = QTextEdit()
        self.ai_prompt.setPlaceholderText(
            "Ej: 'Resuelve la ecuación x^2 - 4 = 0 simbólicamente y grafica la parábola'"
        )
        self.ai_prompt.setFixedHeight(120)
        layout.addWidget(self.ai_prompt)

        file_row = QHBoxLayout()
        self.attached_path_label = QLineEdit()
        self.attached_path_label.setReadOnly(True)
        self.attached_path_label.setPlaceholderText("Ningún archivo adjunto")
        btn_attach = QPushButton("Adjuntar archivo")
        btn_attach.clicked.connect(self.attach_file)
        file_row.addWidget(self.attached_path_label)
        file_row.addWidget(btn_attach)
        layout.addLayout(file_row)

        btn_row = QHBoxLayout()
        btn_gen = QPushButton("Generar código")
        btn_gen.clicked.connect(lambda: self.ai_generate(auto_run=False))
        btn_gen_run = QPushButton("Generar y ejecutar")
        btn_gen_run.clicked.connect(lambda: self.ai_generate(auto_run=True))
        btn_row.addWidget(btn_gen)
        btn_row.addWidget(btn_gen_run)
        layout.addLayout(btn_row)

        layout.addStretch()
        self.ai_dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_dock)
        self._attached_text = ""

    # ---------- Acciones de archivo ----------
    def new_file(self):
        self.editor.clear()
        self.current_file = None

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Python (*.py);;Todos (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.current_file = path

    def save_file(self):
        path = self.current_file
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Guardar", "", "Python (*.py)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.current_file = path

    def attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar archivo", "", "Todos (*)")
        if path:
            self.attached_path_label.setText(path)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    self._attached_text = f.read()[:20000]
            except Exception:
                self._attached_text = ""

    # ---------- Ejecución ----------
    def run_code(self):
        code = self.editor.toPlainText()
        if not code.strip():
            return
        self.console.appendPlainText(">>> Ejecutando...")
        self.worker = ExecutionWorker(code, self.shared_namespace)
        self.worker.output_ready.connect(self.on_output)
        self.worker.error_ready.connect(self.on_error)
        self.worker.figures_ready.connect(self.on_figures)
        self.worker.start()

    def on_output(self, text):
        if text:
            self.console.appendPlainText(text)

    def on_error(self, text):
        self.console.appendPlainText(f"--- ERROR ---\n{text}")

    def on_figures(self, figures):
        self.plot_tabs.clear()
        for i, fig in enumerate(figures):
            canvas = FigureCanvas(fig)
            self.plot_tabs.addTab(canvas, f"Figura {i+1}")
        if figures:
            self.tabs.setCurrentWidget(self.plot_tabs)

    # ---------- IA / Vibecoding ----------
    def ai_generate(self, auto_run: bool):
        prompt = self.ai_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Falta prompt", "Escribe una descripción o instrucción.")
            return
        try:
            code = generate_code(prompt, attached_file_text=self._attached_text)
        except AIAssistantError as e:
            QMessageBox.critical(self, "Error del asistente", str(e))
            return

        self.editor.setPlainText(code)
        self.console.appendPlainText(">>> Código generado por IA insertado en el editor.")
        if auto_run:
            self.run_code()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
