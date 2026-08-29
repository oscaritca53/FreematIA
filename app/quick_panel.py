"""
Panel de entrada rápida: un chat real (multi-turno) con la IA, integrado
sobre la consola. Se abre con Ctrl+Shift+Space. Puedes conversar, adjuntar
un archivo, pedir código, pedir correcciones sobre lo último que generó,
y traer el código a la consola cuando quieras.

Es una herramienta de productividad más de la app -- no está oculta de
forma permanente ni diseñada para pasar desapercibida en pantalla
compartida o grabaciones; simplemente no ocupa espacio fijo en la barra
de herramientas, igual que la paleta de comandos de VS Code (Ctrl+Shift+P).
"""
import html

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser, QLineEdit,
    QPushButton, QLabel, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from code_insight import ChatWorker, extract_code_block


class QuickPanel(QWidget):
    insert_target = None
    run_target = None

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowTitle("Entrada rápida")
        self.resize(560, 520)
        self.messages: list[dict] = []
        self.pending_attachment = ""
        self.worker = None

        self.setStyleSheet(
            "QWidget { background:#252526; color:#e0e0e0; border-radius:8px; }"
            "QTextEdit, QLineEdit, QTextBrowser { background:#1e1e1e; color:#e0e0e0; "
            "border:1px solid #3c3c3c; border-radius:4px; padding:4px; }"
            "QPushButton { background:#3c3c3c; color:#e0e0e0; border:none; "
            "border-radius:4px; padding:6px 10px; }"
            "QPushButton:hover { background:#4a4a4a; }"
            "QPushButton:disabled { color:#777; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Chat (Esc para cerrar)"))
        top_row.addStretch()
        btn_new_chat = QPushButton("Nueva conversación")
        btn_new_chat.clicked.connect(self._new_conversation)
        top_row.addWidget(btn_new_chat)
        layout.addLayout(top_row)

        self.chat_log = QTextBrowser()
        self.chat_log.setOpenExternalLinks(False)
        layout.addWidget(self.chat_log, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#999;")
        layout.addWidget(self.status_label)

        input_row = QHBoxLayout()
        self.input_edit = QTextEdit()
        self.input_edit.setFont(QFont("Consolas", 10))
        self.input_edit.setFixedHeight(70)
        self.input_edit.setPlaceholderText(
            "Escribe tu mensaje... (Ctrl+Enter para enviar)"
        )
        input_row.addWidget(self.input_edit)
        layout.addLayout(input_row)

        file_row = QHBoxLayout()
        self.file_label = QLineEdit()
        self.file_label.setReadOnly(True)
        self.file_label.setPlaceholderText("Sin archivo adjunto")
        btn_attach = QPushButton("Adjuntar")
        btn_attach.clicked.connect(self._attach_file)
        btn_send = QPushButton("Enviar")
        btn_send.clicked.connect(self._send)
        file_row.addWidget(self.file_label)
        file_row.addWidget(btn_attach)
        file_row.addWidget(btn_send)
        layout.addLayout(file_row)

        btn_row = QHBoxLayout()
        self.btn_insert = QPushButton("Insertar último código")
        self.btn_insert.clicked.connect(self._on_insert_last)
        self.btn_run = QPushButton("Insertar y ejecutar")
        self.btn_run.clicked.connect(self._on_run_last)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.hide)
        btn_row.addWidget(self.btn_insert)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._send)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._send)

    # ---------- chat ----------
    def _append_chat(self, sender: str, text: str, color: str):
        safe = html.escape(text).replace("\n", "<br>")
        self.chat_log.append(f'<b style="color:{color}">{sender}:</b> {safe}<br>')

    def _send(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        content_for_model = text
        if self.pending_attachment:
            content_for_model += f"\n\n--- Archivo adjunto ---\n{self.pending_attachment}"
            self.pending_attachment = ""
            self.file_label.clear()

        self._append_chat("Tú", text, "#6cb6ff")
        self.messages.append({"role": "user", "content": content_for_model})
        self.input_edit.clear()
        self.status_label.setText("Pensando...")
        self._set_enabled(False)

        self.worker = ChatWorker(list(self.messages))
        self.worker.reply_ready.connect(self._on_reply)
        self.worker.error_raised.connect(self._on_error)
        self.worker.start()

    def _on_reply(self, reply: str):
        self.messages.append({"role": "assistant", "content": reply})
        self._append_chat("IA", reply, "#7ee787")
        self.status_label.setText("")
        self._set_enabled(True)

    def _on_error(self, msg: str):
        self._append_chat("Sistema", f"Error: {msg}", "#ff8080")
        self.status_label.setText("")
        self._set_enabled(True)

    def _set_enabled(self, enabled: bool):
        self.btn_insert.setEnabled(enabled)
        self.btn_run.setEnabled(enabled)

    def _new_conversation(self):
        self.messages.clear()
        self.chat_log.clear()
        self.status_label.setText("")

    # ---------- archivo adjunto ----------
    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar archivo")
        if path:
            self.file_label.setText(path)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    self.pending_attachment = f.read()[:20000]
            except Exception:
                self.pending_attachment = ""

    # ---------- insertar código de la última respuesta ----------
    def _last_assistant_code(self):
        for m in reversed(self.messages):
            if m["role"] == "assistant":
                return extract_code_block(m["content"])
        return None

    def _on_insert_last(self):
        code = self._last_assistant_code()
        if not code:
            self.status_label.setText("Aún no hay ninguna respuesta con código.")
            return
        if self.insert_target:
            self.insert_target(code)

    def _on_run_last(self):
        code = self._last_assistant_code()
        if not code:
            self.status_label.setText("Aún no hay ninguna respuesta con código.")
            return
        if self.run_target:
            self.run_target(code)

    # ---------- posicionamiento ----------
    def show_over(self, main_window):
        geo = main_window.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + 60
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_edit.setFocus()
