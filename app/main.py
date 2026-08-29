"""
FreeMat AI Studio
Command Window estilo FreeMat con motor Python (numpy/scipy/sympy/matplotlib)
y autocompletado avanzado en segundo plano (Gemini u Ollama local).
"""
import sys
import os
import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QTreeView, QListWidget,
    QTableWidget, QTableWidgetItem, QToolBar, QComboBox, QLabel, QLineEdit,
    QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMdiArea,
    QMdiSubWindow, QCheckBox, QFileSystemModel, QDialog, QDialogButtonBox,
    QMessageBox, QRadioButton, QButtonGroup, QTextEdit, QFrame
)
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QDir

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from command_window import CommandWindow
from mengine import m_engine as mengine
from code_insight import SuggestionWorker
from script_editor import ScriptEditorWindow
from quick_panel import QuickPanel
import config
import icons
import ollama_manager


def _hline():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


class OllamaSetupDialog(QDialog):
    """Diálogo de progreso para 'Preparar IA local': detecta Ollama, arranca
    el servidor si hace falta, y descarga el modelo configurado."""
    def __init__(self, base_url, model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preparando IA local")
        self.resize(480, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Modelo: {model}\nServidor: {base_url}"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(self.font())
        layout.addWidget(self.log)
        self.close_btn = QPushButton("Cerrar")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setEnabled(False)
        layout.addWidget(self.close_btn)

        self.worker = ollama_manager.OllamaSetupWorker(base_url, model)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_setup.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, msg):
        self.log.append(msg)

    def _on_finished(self, ok, msg):
        self.log.append("✓ " + msg if ok else "✗ " + msg)
        self.close_btn.setEnabled(True)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.resize(460, 380)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Proveedor a usar para sugerencias/generación:"))
        radio_row = QHBoxLayout()
        self.radio_cloud = QRadioButton("Nube (Gemini)")
        self.radio_local = QRadioButton("Local (Ollama)")
        group = QButtonGroup(self)
        group.addButton(self.radio_cloud)
        group.addButton(self.radio_local)
        if config.get_provider() == "local":
            self.radio_local.setChecked(True)
        else:
            self.radio_cloud.setChecked(True)
        radio_row.addWidget(self.radio_cloud)
        radio_row.addWidget(self.radio_local)
        radio_row.addStretch()
        layout.addLayout(radio_row)

        layout.addWidget(_hline())
        layout.addWidget(QLabel("<b>Nube (Gemini)</b> — requiere internet y clave gratuita"))
        self.key_edit = QLineEdit(config.get_api_key() or "")
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Clave de aistudio.google.com/apikey")
        layout.addWidget(self.key_edit)
        show_row = QHBoxLayout()
        self.show_check = QCheckBox("Mostrar clave")
        self.show_check.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        show_row.addWidget(self.show_check)
        show_row.addStretch()
        layout.addLayout(show_row)

        layout.addWidget(_hline())
        layout.addWidget(QLabel(
            "<b>Local (Ollama)</b> — sin internet ni clave, corre en tu PC."
        ))
        layout.addWidget(QLabel("URL del servidor:"))
        self.local_url_edit = QLineEdit(config.get_local_url())
        layout.addWidget(self.local_url_edit)
        layout.addWidget(QLabel("Nombre del modelo (ej. qwen2.5-coder:7b, llama3.2):"))
        self.local_model_edit = QLineEdit(config.get_local_model())
        layout.addWidget(self.local_model_edit)

        self.prepare_btn = QPushButton("Preparar IA local (instalar servidor + modelo)")
        self.prepare_btn.clicked.connect(self._prepare_local)
        layout.addWidget(self.prepare_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _prepare_local(self):
        url = self.local_url_edit.text().strip() or "http://localhost:11434"
        model = self.local_model_edit.text().strip() or "qwen2.5-coder:7b"
        dlg = OllamaSetupDialog(url, model, self)
        dlg.exec()

    def _save(self):
        config.set_api_key(self.key_edit.text())
        config.set_provider("local" if self.radio_local.isChecked() else "cloud")
        config.set_local_url(self.local_url_edit.text())
        config.set_local_model(self.local_model_edit.text())
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreeMat AI Studio - Command Window")
        self.resize(1400, 850)
        self.namespace = mengine.make_namespace()
        self.suggestion_worker = None
        self.script_windows = []
        self.plot_windows = []
        self.current_dir = os.path.expanduser("~")

        self._build_command_window()
        self._build_docks()
        self._build_toolbar()
        self._build_menu()
        self._build_quick_panel()

        self._session_banner()
        self.command_window.new_prompt()

    # ---------- construcción de UI ----------
    def _build_command_window(self):
        self.command_window = CommandWindow()
        self.command_window.command_entered.connect(self.on_command_entered)
        self.command_window.input_changed.connect(self.on_input_changed)
        self.setCentralWidget(self.command_window)

    def _build_quick_panel(self):
        self.quick_panel = QuickPanel(self)
        self.quick_panel.insert_target = self.command_window.insert_text
        self.quick_panel.run_target = self.command_window.submit_text

        self.quick_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Space"), self)
        self.quick_shortcut.activated.connect(self._toggle_quick_panel)

    def _toggle_quick_panel(self):
        if self.quick_panel.isVisible():
            self.quick_panel.hide()
        else:
            self.quick_panel.show_over(self)

    def _build_docks(self):
        self.fb_dock = QDockWidget("File Browser", self)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self.current_dir)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.fs_model)
        self.file_tree.setRootIndex(self.fs_model.index(self.current_dir))
        self.file_tree.doubleClicked.connect(self._file_double_clicked)
        self.fb_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.fb_dock)

        self.hist_dock = QDockWidget("History", self)
        self.history_list = QListWidget()
        self.hist_dock.setWidget(self.history_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.hist_dock)

        self.var_dock = QDockWidget("Variables", self)
        self.var_table = QTableWidget(0, 3)
        self.var_table.setHorizontalHeaderLabels(["Name", "Class", "Value"])
        self.var_dock.setWidget(self.var_table)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.var_dock)

        self.debug_dock = QDockWidget("Debug", self)
        self.debug_list = QListWidget()
        self.debug_dock.setWidget(self.debug_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.debug_dock)

        self.splitDockWidget(self.fb_dock, self.hist_dock, Qt.Vertical)
        self.splitDockWidget(self.hist_dock, self.var_dock, Qt.Vertical)
        self.splitDockWidget(self.var_dock, self.debug_dock, Qt.Vertical)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        def add(icon, text, slot, tip=""):
            act = QAction(icon, text, self)
            act.setToolTip(tip or text)
            act.triggered.connect(slot)
            tb.addAction(act)
            return act

        add(icons.new_script(), "Nuevo script", self.new_script, "Nuevo script")
        add(icons.open_folder(), "Abrir", self.open_script, "Abrir archivo")
        add(icons.save(), "Guardar", self.save_active_script, "Guardar")
        tb.addSeparator()
        add(icons.copy_icon(), "Copiar", self.command_window.copy, "Copiar selección")
        add(icons.paste_icon(), "Pegar", self.command_window.paste, "Pegar en la consola")
        add(icons.terminal_icon(), "Consola", lambda: self.command_window.setFocus(),
            "Ir a la consola")
        tb.addSeparator()
        add(icons.pause_icon(), "Pausa", lambda: None,
            "Pausar ejecución (no implementado aún)")
        add(icons.step_icon(), "Step", lambda: None,
            "Ejecutar paso a paso (no implementado aún)")
        add(icons.stop_icon(), "Stop", lambda: None,
            "Detener ejecución (no implementado aún)")
        tb.addSeparator()
        add(icons.loop_arrow_icon(flip=True), "Deshacer", self.command_window.undo, "Deshacer")
        add(icons.loop_arrow_icon(flip=False), "Rehacer", self.command_window.redo, "Rehacer")

        tb.addWidget(QLabel("  Stack: "))
        stack_combo = QComboBox()
        stack_combo.addItem("base")
        tb.addWidget(stack_combo)

        tb.addSeparator()
        self.path_edit = QLineEdit(self.current_dir)
        self.path_edit.setMinimumWidth(260)
        self.path_edit.returnPressed.connect(self._path_edited)
        tb.addWidget(self.path_edit)
        add(icons.open_folder(), "Explorar", self._browse_dir, "Elegir carpeta")
        add(icons.up_arrow_icon(), "Subir", self._go_up, "Subir un nivel")

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        file_menu.addAction("Nuevo script", self.new_script)
        file_menu.addAction("Abrir...", self.open_script)
        file_menu.addAction("Salir", self.close)

        edit_menu = mb.addMenu("Edit")
        edit_menu.addAction("Limpiar consola", self._clear_console)

        debug_menu = mb.addMenu("Debug")
        debug_menu.addAction("Detener ejecución", lambda: None)

        tools_menu = mb.addMenu("Tools")
        self.suggestions_action = QAction("Sugerencias en línea", self, checkable=True)
        self.suggestions_action.setChecked(True)
        tools_menu.addAction(self.suggestions_action)
        tools_menu.addAction("Entrada rápida\tCtrl+Shift+Space", self._toggle_quick_panel)
        tools_menu.addAction("Configuración...", self.open_settings)

        mb.addMenu("Help")

    def _session_banner(self):
        banner = (
            " FreeMat AI Studio v1.0\n"
            " Sintaxis .m (subconjunto MATLAB/FreeMat) sobre NumPy/Matplotlib\n"
            " Escribe 'help' para ayuda básica.\n"
        )
        self.command_window.write(banner)
        ts = datetime.datetime.now().strftime("%a %d. %b %H:%M:%S %Y")
        self.history_list.addItem(f"%% {ts}")

    def _clear_console(self):
        self.command_window.clear()
        self.command_window.new_prompt()

    def on_command_entered(self, code: str):
        if not code.strip():
            self.command_window.new_prompt()
            return
        if code.strip() == "help":
            self.command_window.write(
                "Sintaxis .m: asignaciones, if/for/while/switch, function...end,\n"
                "matrices [1 2; 3 4], indexado A(i,j) desde 1, A(end).\n"
                "Funciones: zeros, ones, eye, rand, size, length, disp, fprintf,\n"
                "sum, mean, max, min, sort, find, sin/cos/..., plot, figure.\n"
            )
            self.command_window.new_prompt()
            return

        output, error, figures = mengine.run(code, self.namespace)
        if output:
            self.command_window.write(output if output.endswith("\n") else output + "\n")
        if error:
            self.command_window.write(error if error.endswith("\n") else error + "\n")

        self.history_list.addItem(code)
        self._refresh_variables()
        self._show_figures(figures)
        self.command_window.new_prompt()

    def run_script_code(self, code: str):
        output, error, figures = mengine.run(code, self.namespace)
        if output:
            self.command_window.write(output if output.endswith("\n") else output + "\n")
        if error:
            self.command_window.write(error if error.endswith("\n") else error + "\n")
        self._refresh_variables()
        self._show_figures(figures)
        self.command_window.new_prompt()

    def _refresh_variables(self):
        rows = mengine.visible_variables(self.namespace)
        self.var_table.setRowCount(len(rows))
        for i, (name, cls, val) in enumerate(rows):
            self.var_table.setItem(i, 0, QTableWidgetItem(name))
            self.var_table.setItem(i, 1, QTableWidgetItem(cls))
            self.var_table.setItem(i, 2, QTableWidgetItem(val))

    def _show_figures(self, figures):
        for fig in figures:
            win = QMainWindow()
            win.setWindowTitle(f"Figure {fig.number}")
            canvas = FigureCanvas(fig)
            win.setCentralWidget(canvas)
            win.resize(600, 450)
            win.show()
            self.plot_windows.append(win)

    def on_input_changed(self, current_line: str):
        if not self.suggestions_action.isChecked():
            return
        if not current_line.strip():
            return
        history_texts = [self.history_list.item(i).text()
                          for i in range(self.history_list.count())][-6:]
        self.suggestion_worker = SuggestionWorker(current_line, history_texts)
        self.suggestion_worker.suggestion_ready.connect(self._on_suggestion_ready)
        self.suggestion_worker.start()

    def _on_suggestion_ready(self, requested_for: str, suggestion: str):
        if requested_for != self.command_window.current_input():
            return
        self.command_window.show_ghost(suggestion)

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def new_script(self):
        win = ScriptEditorWindow()
        win.run_requested.connect(self.run_script_code)
        win.show()
        self.script_windows.append(win)

    def open_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir", self.current_dir,
            "Scripts FreeMat (*.m);;Python (*.py);;Todos (*)"
        )
        if path:
            win = ScriptEditorWindow(path)
            win.run_requested.connect(self.run_script_code)
            win.show()
            self.script_windows.append(win)

    def save_active_script(self):
        if self.script_windows:
            self.script_windows[-1].save()

    def _file_double_clicked(self, index):
        path = self.fs_model.filePath(index)
        if os.path.isfile(path) and path.endswith((".m", ".py")):
            win = ScriptEditorWindow(path)
            win.run_requested.connect(self.run_script_code)
            win.show()
            self.script_windows.append(win)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Elegir carpeta", self.current_dir)
        if path:
            self._set_dir(path)

    def _go_up(self):
        parent = os.path.dirname(self.current_dir.rstrip(os.sep))
        if parent:
            self._set_dir(parent)

    def _path_edited(self):
        path = self.path_edit.text().strip()
        if os.path.isdir(path):
            self._set_dir(path)

    def _set_dir(self, path):
        self.current_dir = path
        self.path_edit.setText(path)
        self.file_tree.setRootIndex(self.fs_model.index(path))


def _apply_light_theme(app):
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f0f0f0"))
    palette.setColor(QPalette.WindowText, QColor("#000000"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f5f5f5"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffe1"))
    palette.setColor(QPalette.ToolTipText, QColor("#000000"))
    palette.setColor(QPalette.Text, QColor("#000000"))
    palette.setColor(QPalette.Button, QColor("#f0f0f0"))
    palette.setColor(QPalette.ButtonText, QColor("#000000"))
    palette.setColor(QPalette.BrightText, QColor("#ff0000"))
    palette.setColor(QPalette.Highlight, QColor("#3399ff"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _apply_light_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
