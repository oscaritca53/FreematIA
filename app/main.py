"""
FreeMat AI Studio
Command Window estilo FreeMat con motor Python (numpy/scipy/sympy/matplotlib)
y autocompletado avanzado en segundo plano (Gemini, capa gratuita).
"""
import sys
import os
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mengine"))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QTreeView, QListWidget,
    QTableWidget, QTableWidgetItem, QToolBar, QComboBox, QLabel, QLineEdit,
    QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMdiArea,
    QMdiSubWindow, QCheckBox, QFileSystemModel, QDialog, QDialogButtonBox,
    QMessageBox
)
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QDir

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from command_window import CommandWindow
import m_engine as mengine
from code_insight import SuggestionWorker
from script_editor import ScriptEditorWindow
from quick_panel import QuickPanel
import config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.resize(420, 140)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Clave de servicio (opcional).\n"
            "Habilita sugerencias mientras escribes en la consola."
        ))
        self.key_edit = QLineEdit(config.get_api_key() or "")
        self.key_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.key_edit)

        show_row = QHBoxLayout()
        self.show_check = QCheckBox("Mostrar")
        self.show_check.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        show_row.addWidget(self.show_check)
        show_row.addStretch()
        layout.addLayout(show_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        config.set_api_key(self.key_edit.text())
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
        # File Browser
        self.fb_dock = QDockWidget("File Browser", self)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self.current_dir)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.fs_model)
        self.file_tree.setRootIndex(self.fs_model.index(self.current_dir))
        self.file_tree.doubleClicked.connect(self._file_double_clicked)
        self.fb_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.fb_dock)

        # History
        self.hist_dock = QDockWidget("History", self)
        self.history_list = QListWidget()
        self.hist_dock.setWidget(self.history_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.hist_dock)

        # Variables
        self.var_dock = QDockWidget("Variables", self)
        self.var_table = QTableWidget(0, 3)
        self.var_table.setHorizontalHeaderLabels(["Name", "Class", "Value"])
        self.var_dock.setWidget(self.var_table)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.var_dock)

        # Debug
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
        style = self.style()

        def add(icon, text, slot, tip=""):
            act = QAction(style.standardIcon(icon), text, self)
            act.setToolTip(tip or text)
            act.triggered.connect(slot)
            tb.addAction(act)
            return act

        from PySide6.QtWidgets import QStyle
        add(QStyle.SP_FileIcon, "Nuevo script", self.new_script, "Nuevo script")
        add(QStyle.SP_DialogOpenButton, "Abrir", self.open_script, "Abrir archivo")
        add(QStyle.SP_DialogSaveButton, "Guardar", self.save_active_script, "Guardar")
        tb.addSeparator()
        add(QStyle.SP_MediaPause, "Pausa", lambda: None, "Pausar ejecución")
        add(QStyle.SP_MediaSkipForward, "Step", lambda: None, "Step")
        add(QStyle.SP_MediaStop, "Stop", lambda: None, "Detener")
        tb.addSeparator()

        tb.addWidget(QLabel("  Stack: "))
        stack_combo = QComboBox()
        stack_combo.addItem("base")
        tb.addWidget(stack_combo)

        tb.addSeparator()
        self.path_edit = QLineEdit(self.current_dir)
        self.path_edit.setMinimumWidth(260)
        self.path_edit.returnPressed.connect(self._path_edited)
        tb.addWidget(self.path_edit)
        add(QStyle.SP_DirIcon, "Explorar", self._browse_dir, "Elegir carpeta")
        add(QStyle.SP_ArrowUp, "Subir", self._go_up, "Subir un nivel")

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
        # ^ Deliberadamente sin mencionar el proveedor ni "IA" en el texto visible.

        mb.addMenu("Help")

    # ---------- banner y utilidades de consola ----------
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

    # ---------- ejecución ----------
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

    # ---------- autocompletado en segundo plano (oculto) ----------
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
        # Evita mostrar sugerencias obsoletas si el usuario ya siguió escribiendo
        if requested_for != self.command_window.current_input():
            return
        self.command_window.show_ghost(suggestion)

    # ---------- configuración ----------
    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    # ---------- archivos (.m, al estilo FreeMat) ----------
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


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
