"""
Panel de acceso rápido (tipo Spotlight/paleta de comandos): se abre con un
atajo de teclado sobre la ventana principal. Permite escribir un prompt o
adjuntar un archivo, generar código .m y llevarlo a la consola.

Es una herramienta de productividad más de la app -- no está oculta de
forma permanente ni diseñada para pasar desapercibida en pantalla
compartida o grabaciones; simplemente no ocupa espacio fijo en la barra
de herramientas, igual que la paleta de comandos de VS Code (Ctrl+Shift+P).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
    QLabel, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from code_insight import GenerationWorker


class QuickPanel(QWidget):
    insert_target = None
    run_target = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowTitle("Entrada rápida")
        self.resize(520, 260)
        self.attached_text = ""
        self.worker = None

        self.setStyleSheet(
            "QWidget { background:#252526; color:#e0e0e0; border-radius:8px; }"
            "QTextEdit, QLineEdit { background:#1e1e1e; color:#e0e0e0; "
            "border:1px solid #3c3c3c; border-radius:4px; padding:4px; }"
            "QPushButton { background:#3c3c3c; color:#e0e0e0; border:none; "
            "border-radius:4px; padding:6px 10px; }"
            "QPushButton:hover { background:#4a4a4a; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(QLabel("Escribe qué quieres calcular (Esc para cerrar):"))

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setFont(QFont("Consolas", 10))
        self.prompt_edit.setFixedHeight(90)
        self.prompt_edit.setPlaceholderText(
            "Ej: 'Genera una matriz 4x4 aleatoria y calcula su determinante'"
        )
        layout.addWidget(self.prompt_edit)

        file_row = QHBoxLayout()
        self.file_label = QLineEdit()
        self.file_label.setReadOnly(True)
        self.file_label.setPlaceholderText("Sin archivo adjunto")
        btn_attach = QPushButton("Adjuntar")
        btn_attach.clicked.connect(self._attach_file)
        file_row.addWidget(self.file_label)
        file_row.addWidget(btn_attach)
        layout.addLayout(file_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#999;")
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.btn_insert = QPushButton("Insertar en consola")
        self.btn_insert.clicked.connect(self._on_insert)
        self.btn_run = QPushButton("Insertar y ejecutar")
        self.btn_run.clicked.connect(self._on_run)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.hide)
        btn_row.addWidget(self.btn_insert)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        QShortcut(QKeySequence("Esc"), self, activated=self.hide)

    # ---------- acciones ----------
    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar archivo")
        if path:
            self.file_label.setText(path)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    self.attached_text = f.read()[:20000]
            except Exception:
                self.attached_text = ""

    def _generate(self, callback):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            self.status_label.setText("Escribe una instrucción primero.")
            return
        self.status_label.setText("Generando...")
        self.btn_insert.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.worker = GenerationWorker(prompt, self.attached_text)
        self.worker.result_ready.connect(lambda code: self._on_result(code, callback))
        self.worker.error_raised.connect(self._on_error)
        self.worker.start()

    def _on_result(self, code, callback):
        self.status_label.setText("Listo.")
        self.btn_insert.setEnabled(True)
        self.btn_run.setEnabled(True)
        callback(code)

    def _on_error(self, msg):
        self.status_label.setText(f"Error: {msg}")
        self.btn_insert.setEnabled(True)
        self.btn_run.setEnabled(True)

    def _on_insert(self):
        self._generate(self._insert_callback)

    def _on_run(self):
        self._generate(self._run_callback)

    def _insert_callback(self, code):
        if self.insert_target:
            self.insert_target(code)
        self.hide()

    def _run_callback(self, code):
        if self.run_target:
            self.run_target(code)
        self.hide()

    # ---------- posicionamiento ----------
    def show_over(self, main_window):
        geo = main_window.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + 100
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.prompt_edit.setFocus()
