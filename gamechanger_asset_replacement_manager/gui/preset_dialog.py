"""Dialog to create, edit, or delete path presets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from gui.theme import Theme


class PresetManagerDialog(QDialog):
    def __init__(self, presets: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Path Presets")
        self.resize(560, 400)
        self._presets = dict(presets)

        intro = QLabel(
            "Save frequently used source folders for quick selection on the Source Files screen."
        )
        intro.setWordWrap(True)
        intro.setProperty("class", "muted")

        self._list = QListWidget()
        self._refresh_list()

        self._name = QLineEdit()
        self._path = QLineEdit()

        save_btn = QPushButton("Save Preset")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save_preset)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self._delete_preset)

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("Preset name:", self._name)
        form.addRow("Folder path:", self._path)

        btn_row = QHBoxLayout()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(delete_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(intro)
        layout.addWidget(self._list)
        layout.addLayout(form)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._list.currentTextChanged.connect(self._on_select)

    def _refresh_list(self) -> None:
        self._list.clear()
        for name in sorted(self._presets.keys()):
            self._list.addItem(name)

    def _on_select(self, name: str) -> None:
        if name in self._presets:
            self._name.setText(name)
            self._path.setText(self._presets[name])

    def _save_preset(self) -> None:
        name = self._name.text().strip()
        path = self._path.text().strip()
        if not name or not path:
            QMessageBox.warning(self, "Preset", "Name and path are required.")
            return
        self._presets[name] = path
        self._refresh_list()
        items = self._list.findItems(name, 0)
        if items:
            self._list.setCurrentItem(items[0])

    def _delete_preset(self) -> None:
        name = self._name.text().strip() or (
            self._list.currentItem().text() if self._list.currentItem() else ""
        )
        if not name or name not in self._presets:
            return
        del self._presets[name]
        self._name.clear()
        self._path.clear()
        self._refresh_list()

    def presets(self) -> dict[str, str]:
        return dict(self._presets)
