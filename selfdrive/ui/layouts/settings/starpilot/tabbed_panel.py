from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pyray as rl

from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import Widget

from openpilot.selfdrive.ui.layouts.settings.starpilot.aethergrid import RadioTileGroup


@dataclass(frozen=True)
class TabSectionSpec:
  key: str
  label: str
  panel: Widget


class TabbedSectionHost(Widget):
  def __init__(self, sections: list[TabSectionSpec]):
    super().__init__()
    if not sections:
      raise ValueError("TabbedSectionHost requires at least one section")

    self._sections = {spec.key: spec.panel for spec in sections}
    self._section_order = [spec.key for spec in sections]
    self._active_section = self._section_order[0]
    self._navigate_callback: Callable | None = None
    self._back_callback: Callable | None = None
    self._current_sub_panel = ""
    self._tab_height = 110
    self._panel_top = 140
    self._section_tabs = RadioTileGroup("", [tr(spec.label) for spec in sections], 0, self._on_tab_change)

    for key, panel in self._sections.items():
      if hasattr(panel, "set_navigate_callback"):
        panel.set_navigate_callback(lambda sub_panel, section_key=key: self._on_child_navigate(section_key, sub_panel))
      if hasattr(panel, "set_back_callback"):
        panel.set_back_callback(self._go_back)

  def set_navigate_callback(self, callback: Callable):
    self._navigate_callback = callback

  def set_back_callback(self, callback: Callable):
    self._back_callback = callback

  def set_current_sub_panel(self, sub_panel: str):
    self._current_sub_panel = sub_panel
    if not sub_panel:
      panel = self._sections[self._active_section]
      if hasattr(panel, "set_current_sub_panel"):
        panel.set_current_sub_panel("")
      return

    if ":" in sub_panel:
      section_key, child_panel = sub_panel.split(":", 1)
      self._activate_section(section_key, child_panel)
    elif sub_panel in self._sections:
      self._activate_section(sub_panel)
    else:
      panel = self._sections[self._active_section]
      if hasattr(panel, "set_current_sub_panel"):
        panel.set_current_sub_panel(sub_panel)

  def _on_tab_change(self, index: int):
    if 0 <= index < len(self._section_order):
      self._current_sub_panel = ""
      self._activate_section(self._section_order[index], "")
      if self._navigate_callback:
        self._navigate_callback("")

  def _activate_section(self, section_key: str, child_panel: str = ""):
    if section_key not in self._sections:
      return

    previous = self._active_section
    if section_key != previous:
      previous_panel = self._sections[previous]
      if hasattr(previous_panel, "set_current_sub_panel"):
        previous_panel.set_current_sub_panel("")
      self._sections[previous].hide_event()
      self._active_section = section_key
      self._sections[section_key].show_event()

    self._section_tabs.set_index(self._section_order.index(section_key))
    panel = self._sections[section_key]
    if hasattr(panel, "set_current_sub_panel"):
      panel.set_current_sub_panel(child_panel)

  def _on_child_navigate(self, section_key: str, sub_panel: str):
    self._current_sub_panel = f"{section_key}:{sub_panel}" if sub_panel else section_key
    if self._navigate_callback:
      self._navigate_callback(self._current_sub_panel)

  def _go_back(self):
    self._current_sub_panel = ""
    panel = self._sections[self._active_section]
    if hasattr(panel, "set_current_sub_panel"):
      panel.set_current_sub_panel("")
    if self._back_callback:
      self._back_callback()

  def _render(self, rect: rl.Rectangle):
    tab_rect = rl.Rectangle(rect.x, rect.y, rect.width, self._tab_height)
    panel_rect = rl.Rectangle(rect.x, rect.y + self._panel_top, rect.width, rect.height - self._panel_top)
    self._section_tabs.render(tab_rect)
    self._sections[self._active_section].render(panel_rect)

  def show_event(self):
    super().show_event()
    self._section_tabs.show_event()
    self._sections[self._active_section].show_event()

  def hide_event(self):
    super().hide_event()
    self._section_tabs.hide_event()
    self._sections[self._active_section].hide_event()
