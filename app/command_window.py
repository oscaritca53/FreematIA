"""Consola de comandos estilo FreeMat: prompt '-->', historial navegable con
flechas, y sugerencias 'fantasma' (gray ghost text) que se aceptan con Tab."""
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtCore import Qt, Signal, QTimer

PROMPT = "--> "
GHOST_COLOR = "#a6a6a6"
NORMAL_COLOR = "#00008b"


class CommandWindow(QPlainTextEdit):
    command_entered = Signal(str)
    input_changed = Signal(str)  # dispara el debounce de sugerencias

    def __init__(self):
        super().__init__()
        self.setFont(QFont("Consolas" if self._is_windows() else "Monospace", 11))
        self.setStyleSheet("background:#ffffff; color:#00008b; border:none; padding:4px;")
        self.prompt_pos = 0
        self.ghost_start = None
        self.ghost_text = ""
        self.cmd_history: list[str] = []
        self.history_idx = 0

        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.timeout.connect(self._emit_input_changed)

    @staticmethod
    def _is_windows():
        import sys
        return sys.platform == "win32"

    # ---------- utilidades de prompt ----------
    def write(self, text: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def new_prompt(self):
        self.write(("\n" if self.toPlainText() and not self.toPlainText().endswith("\n") else "") + PROMPT)
        self.prompt_pos = len(self.toPlainText())

    def current_input(self) -> str:
        return self.toPlainText()[self.prompt_pos:]

    def _replace_input(self, text: str):
        cursor = self.textCursor()
        cursor.setPosition(self.prompt_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    # ---------- ghost text ----------
    def show_ghost(self, suggestion: str):
        self._clear_ghost()
        if not suggestion:
            return
        cursor = self.textCursor()
        if cursor.position() != len(self.toPlainText()):
            return  # solo si el cursor está al final
        self.ghost_start = cursor.position()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(GHOST_COLOR))
        fmt.setFontItalic(True)
        cursor.insertText(suggestion, fmt)
        cursor.setPosition(self.ghost_start)
        self.setTextCursor(cursor)
        self.ghost_text = suggestion

    def _clear_ghost(self):
        if self.ghost_start is None:
            return
        cursor = self.textCursor()
        cursor.setPosition(self.ghost_start)
        cursor.setPosition(self.ghost_start + len(self.ghost_text), QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.ghost_start = None
        self.ghost_text = ""

    def _accept_ghost(self):
        if self.ghost_start is None:
            return
        cursor = self.textCursor()
        cursor.setPosition(self.ghost_start)
        cursor.setPosition(self.ghost_start + len(self.ghost_text), QTextCursor.KeepAnchor)
        normal = QTextCharFormat()
        normal.setForeground(QColor(NORMAL_COLOR))
        normal.setFontItalic(False)
        cursor.setCharFormat(normal)
        cursor.setPosition(self.ghost_start + len(self.ghost_text))
        self.setTextCursor(cursor)
        self.ghost_start = None
        self.ghost_text = ""

    # ---------- eventos de teclado ----------
    def keyPressEvent(self, event):
        cursor = self.textCursor()

        # No permitir editar antes del prompt
        if cursor.position() < self.prompt_pos and event.key() not in (
            Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down
        ):
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

        if event.key() == Qt.Key_Tab and self.ghost_start is not None:
            self._accept_ghost()
            return

        if self.ghost_start is not None:
            self._clear_ghost()

        if event.key() in (Qt.Key_Backspace,) and self.textCursor().position() <= self.prompt_pos:
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cmd = self.current_input()
            self.write("\n")
            if cmd.strip():
                self.cmd_history.append(cmd)
            self.history_idx = len(self.cmd_history)
            self.command_entered.emit(cmd)
            return

        if event.key() == Qt.Key_Up:
            if self.cmd_history and self.history_idx > 0:
                self.history_idx -= 1
                self._replace_input(self.cmd_history[self.history_idx])
            return

        if event.key() == Qt.Key_Down:
            if self.cmd_history and self.history_idx < len(self.cmd_history) - 1:
                self.history_idx += 1
                self._replace_input(self.cmd_history[self.history_idx])
            else:
                self.history_idx = len(self.cmd_history)
                self._replace_input("")
            return

        super().keyPressEvent(event)

        if event.text():
            self.debounce.start(700)

    def insert_text(self, text: str):
        """Inserta texto en la línea de entrada actual (sin ejecutar)."""
        self._clear_ghost()
        current = self.current_input()
        self._replace_input(current + text)

    def submit_text(self, text: str):
        """Reemplaza la entrada actual por 'text' y la ejecuta, como si el
        usuario la hubiera escrito y presionado Enter."""
        self._clear_ghost()
        self._replace_input(text)
        cmd = self.current_input()
        self.write("\n")
        if cmd.strip():
            self.cmd_history.append(cmd)
        self.history_idx = len(self.cmd_history)
        self.command_entered.emit(cmd)

    def _emit_input_changed(self):
        self.input_changed.emit(self.current_input())
