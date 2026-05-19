"""Workspace artifact controls mixin for MainWindow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout, QFileDialog

from flowscribe.gui.utils import (
    _artifact_compare_group,
    _artifact_format_label,
    _artifact_selector_label,
    _artifact_summary,
    _is_viewable_artifact_path,
    _normalize_viewable_artifact_paths,
    _read_viewable_artifact_text,
    _render_json_artifact_html,
    _sort_workspace_artifact_paths,
    _view_tab_key_for_artifact,
    _view_tab_title_for_artifact,
)


class WorkspaceControlsMixin:
    """Mixin providing workspace artifact viewing and management methods."""

    def _set_workspace_artifact_paths(
        self,
        paths: tuple[Path, ...],
        *,
        replace: bool,
        preferred_path: Path | None = None,
    ) -> None:
        normalized = _sort_workspace_artifact_paths(
            _normalize_viewable_artifact_paths(paths)
        )
        if replace:
            merged = normalized
        else:
            merged = _sort_workspace_artifact_paths(
                _normalize_viewable_artifact_paths(
                    self._workspace_artifact_paths + normalized
                )
            )
        self._workspace_artifact_paths = merged
        selector = self._workspace_artifact_selector
        if selector is None:
            return
        selector.blockSignals(True)
        try:
            selector.clear()
            for path in merged:
                selector.addItem(_artifact_selector_label(path), str(path))
        finally:
            selector.blockSignals(False)

        if not merged:
            if self._workspace_artifact_viewer is not None:
                self._workspace_artifact_viewer.clear()
            if self._workspace_artifact_markdown_viewer is not None:
                self._workspace_artifact_markdown_viewer.clear()
            if self._workspace_artifact_format_label is not None:
                self._workspace_artifact_format_label.setText("No artifact selected")
            if self._workspace_artifact_status_label is not None:
                self._workspace_artifact_status_label.setText(
                    "Open a transcript or artifact to inspect generated files here."
                )
            self._refresh_workspace_artifact_buttons()
            return

        selected_path = preferred_path if preferred_path in merged else merged[0]
        selector.setCurrentIndex(merged.index(selected_path))
        self._show_workspace_artifact(selected_path)

    def _show_selected_workspace_artifact(self, index: int) -> None:
        if index < 0 or index >= len(self._workspace_artifact_paths):
            return
        self._show_workspace_artifact(self._workspace_artifact_paths[index])

    def _refresh_workspace_artifact_buttons(self) -> None:
        for group, button in self._workspace_artifact_quick_buttons.items():
            if button is None:
                continue
            button.setEnabled(
                any(
                    _artifact_compare_group(path) == group
                    for path in self._workspace_artifact_paths
                )
            )

    def _show_workspace_artifact_group(self, group: str) -> None:
        for index, path in enumerate(self._workspace_artifact_paths):
            if _artifact_compare_group(path) != group:
                continue
            if self._workspace_artifact_selector is not None:
                self._workspace_artifact_selector.setCurrentIndex(index)
            self._show_workspace_artifact(path)
            return
        self.status_label.setText(f"No {group.replace('_', ' ')} artifact is available yet.")

    def _show_workspace_artifact(self, path: Path) -> None:
        viewer = self._workspace_artifact_viewer
        markdown_viewer = self._workspace_artifact_markdown_viewer
        viewer_stack = self._workspace_artifact_viewer_stack
        status_label = self._workspace_artifact_status_label
        format_label = self._workspace_artifact_format_label
        if viewer is None or markdown_viewer is None or status_label is None:
            return
        if not path.is_file():
            viewer.clear()
            markdown_viewer.clear()
            if format_label is not None:
                format_label.setText("Missing artifact")
            status_label.setText(f"Artifact is missing: {path}")
            self._refresh_workspace_artifact_buttons()
            return
        rendered = _read_viewable_artifact_text(path)
        if path.suffix.lower() == ".json":
            markdown_viewer.setHtml(_render_json_artifact_html(path, rendered))
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(markdown_viewer)
        elif path.suffix.lower() == ".md":
            markdown_viewer.setMarkdown(rendered)
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(markdown_viewer)
        else:
            viewer.setPlainText(rendered)
            if viewer_stack is not None:
                viewer_stack.setCurrentWidget(viewer)
        if format_label is not None:
            format_label.setText(_artifact_format_label(path))
        status_label.setText(
            f"{_artifact_summary(path, rendered)} | Inspecting {path.name} in the current transcript workspace."
        )
        self._refresh_workspace_artifact_buttons()

    def _open_selected_workspace_artifact_tab(self) -> None:
        selector = self._workspace_artifact_selector
        if selector is None:
            return
        index = selector.currentIndex()
        if index < 0 or index >= len(self._workspace_artifact_paths):
            self.status_label.setText("Select an artifact first.")
            return
        path = self._workspace_artifact_paths[index]
        self._ensure_artifact_view_tab(path)
        self._select_view_tab(_view_tab_key_for_artifact(path))

    def _ensure_artifact_view_tab(self, path: Path) -> None:
        if not _is_viewable_artifact_path(path):
            return
        normalized = path.expanduser().resolve()
        key = _view_tab_key_for_artifact(normalized)
        title = _view_tab_title_for_artifact(normalized)
        viewer = self._artifact_viewers.get(normalized)
        page = self._view_tab_pages.get(key)
        if viewer is None or page is None:
            page = QWidget(self._views_dialog)
            page_layout = QVBoxLayout(page)
            viewer = QPlainTextEdit(page)
            viewer.setReadOnly(True)
            page_layout.addWidget(viewer)
            self._artifact_viewers[normalized] = viewer
            self._view_tab_pages[key] = page
        viewer.setPlainText(_read_viewable_artifact_text(normalized))
        self._view_tab_titles[key] = title
        self._view_tab_visibility[key] = True
        self._set_view_tab_visible(key, True)
        index = self._find_view_tab_index(key)
        if index >= 0:
            self._views_tab_widget.setTabText(index, title)
        self._refresh_view_menu()

    def _clear_artifact_view_tabs(self) -> None:
        artifact_keys = [key for key in self._view_tab_pages if key.startswith("artifact:")]
        for key in artifact_keys:
            page = self._view_tab_pages.get(key)
            if self._views_tab_widget is not None and page is not None:
                index = self._views_tab_widget.indexOf(page)
                if index >= 0:
                    self._views_tab_widget.removeTab(index)
            self._view_tab_pages.pop(key, None)
            self._view_tab_titles.pop(key, None)
            self._view_tab_visibility.pop(key, None)
        self._artifact_viewers = {}
        self._workspace_artifact_paths = ()
        self._set_workspace_artifact_paths((), replace=True)
        self._refresh_view_menu()

    def _load_artifact_views(self, paths: tuple[Path, ...], *, replace: bool = False) -> None:
        normalized_paths = _normalize_viewable_artifact_paths(paths)
        if replace:
            self._clear_artifact_view_tabs()
        for path in normalized_paths:
            if path.is_file():
                self._ensure_artifact_view_tab(path)
        preferred_path = normalized_paths[0] if normalized_paths else None
        self._set_workspace_artifact_paths(
            normalized_paths,
            replace=replace,
            preferred_path=preferred_path,
        )

    def _open_view_artifact(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open transcript artifact",
            self.output_dir_input.text().strip() or "outputs",
            "Viewable artifacts (*.json *.txt *.md *.srt *.vtt)",
        )
        if not path:
            return
        self._open_transcript_or_artifact(Path(path))
