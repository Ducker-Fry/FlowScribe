from __future__ import annotations

from pathlib import Path

from flowscribe.gui.utils.artifacts import (
    _normalize_viewable_artifact_paths,
    _read_viewable_artifact_text,
    _sort_workspace_artifact_paths,
)
from flowscribe.gui.utils.formatting import (
    _artifact_compare_group,
    _artifact_format_label,
    _artifact_selector_label,
    _artifact_summary,
    _render_json_artifact_html,
)


class TranscriptionViewDialogWorkspaceMixin:
    """Workspace artifact viewer helpers for the dialog."""

    def _load_artifacts(self, paths: tuple[Path, ...]) -> None:
        normalized = _sort_workspace_artifact_paths(_normalize_viewable_artifact_paths(paths))
        self._workspace_artifact_paths = normalized

        self.artifact_selector.blockSignals(True)
        try:
            self.artifact_selector.clear()
            for path in normalized:
                self.artifact_selector.addItem(_artifact_selector_label(path), str(path))
        finally:
            self.artifact_selector.blockSignals(False)

        if normalized:
            self._show_workspace_artifact(normalized[0])
            self._refresh_workspace_artifact_buttons()
            return

        self._set_workspace_status("No artifacts found. Generate output files to view them here.")

    def _refresh_workspace_artifact_buttons(self) -> None:
        for group, button in self._workspace_artifact_quick_buttons.items():
            button.setEnabled(
                any(_artifact_compare_group(path) == group for path in self._workspace_artifact_paths)
            )

    def _show_selected_workspace_artifact(self, index: int) -> None:
        if index < 0 or index >= len(self._workspace_artifact_paths):
            return
        self._show_workspace_artifact(self._workspace_artifact_paths[index])

    def _show_workspace_artifact(self, path: Path) -> None:
        if not path.is_file():
            self.artifact_viewer.clear()
            self.artifact_markdown_viewer.clear()
            self.artifact_format_label.setText("Missing artifact")
            self._set_workspace_status(f"Artifact is missing: {path}")
            self._refresh_workspace_artifact_buttons()
            return

        rendered = _read_viewable_artifact_text(path)
        if path.suffix.lower() == ".json":
            self.artifact_markdown_viewer.setHtml(_render_json_artifact_html(path, rendered))
            self._workspace_artifact_viewer_stack.setCurrentWidget(self.artifact_markdown_viewer)
        elif path.suffix.lower() == ".md":
            self.artifact_markdown_viewer.setMarkdown(rendered)
            self._workspace_artifact_viewer_stack.setCurrentWidget(self.artifact_markdown_viewer)
        else:
            self.artifact_viewer.setPlainText(rendered)
            self._workspace_artifact_viewer_stack.setCurrentWidget(self.artifact_viewer)

        self.artifact_format_label.setText(_artifact_format_label(path))
        self._set_workspace_status(f"{_artifact_summary(path, rendered)} | Opened artifact: {path.name}")
        self._refresh_workspace_artifact_buttons()

    def _show_workspace_artifact_group(self, group: str) -> None:
        for index, path in enumerate(self._workspace_artifact_paths):
            if _artifact_compare_group(path) != group:
                continue
            self.artifact_selector.setCurrentIndex(index)
            self._show_workspace_artifact(path)
            return
        self._set_workspace_status(f"No {group.replace('_', ' ')} artifact is available yet.")

    def _open_selected_workspace_artifact_tab(self) -> None:
        index = self.artifact_selector.currentIndex()
        if index < 0 or index >= len(self._workspace_artifact_paths):
            self._set_workspace_status("Select an artifact first.")
            return
        self._show_workspace_artifact(self._workspace_artifact_paths[index])
