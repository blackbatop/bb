from __future__ import annotations

from dataclasses import dataclass

import pyray as rl

from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

from openpilot.selfdrive.ui.layouts.settings.starpilot.aethergrid import SPACING, TileGrid


@dataclass(frozen=True)
class TileSection:
  title: str
  grid: TileGrid


class SectionedTileLayout(Widget):
  def __init__(self, section_gap: int = SPACING.section_gap, title_height: int = 32, title_gap: int = SPACING.sm,
               min_row_height: int = 150, max_row_height: int = 280, top_padding: int = 0,
               horizontal_padding: int = SPACING.xl, max_content_width: int | None = 1440):
    super().__init__()
    self._sections: list[TileSection] = []
    self._section_gap = section_gap
    self._title_height = title_height
    self._title_gap = title_gap
    self._min_row_height = min_row_height
    self._max_row_height = max_row_height
    self._top_padding = top_padding
    self._horizontal_padding = horizontal_padding
    self._max_content_width = max_content_width
    self._title_font_size = 26
    self._font_title = gui_app.font(FontWeight.BOLD)
    self._is_active = False

  def set_sections(self, sections: list[TileSection]):
    if self._is_active:
      for section in self._sections:
        section.grid.hide_event()
    self._sections = list(sections)
    if self._is_active:
      for section in self._sections:
        section.grid.show_event()

  def clear(self):
    self._sections.clear()

  def show_event(self):
    self._is_active = True
    super().show_event()
    for section in self._sections:
      section.grid.show_event()

  def hide_event(self):
    self._is_active = False
    super().hide_event()
    for section in self._sections:
      section.grid.hide_event()

  def _title_block_height(self, section: TileSection) -> int:
    return (self._title_height + self._title_gap) if section.title else 0

  def _section_band_height(self, section: TileSection, row_height: float) -> float:
    rows = section.grid.get_row_count()
    if rows <= 0:
      return 0.0
    return (rows * row_height) + (section.grid.gap * max(0, rows - 1))

  def _content_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
    content_x = rect.x + self._horizontal_padding
    content_w = max(0.0, rect.width - (self._horizontal_padding * 2))
    if self._max_content_width is not None and content_w > self._max_content_width:
      content_w = float(self._max_content_width)
      content_x = rect.x + (rect.width - content_w) / 2
    return rl.Rectangle(content_x, rect.y, content_w, rect.height)

  def _compute_row_height(self, rect: rl.Rectangle, sections: list[TileSection]) -> float:
    total_rows = sum(section.grid.get_row_count() for section in sections)
    if total_rows <= 0:
      return 0.0

    total_title_height = sum(self._title_block_height(section) for section in sections)
    total_section_gaps = self._section_gap * max(0, len(sections) - 1)
    total_internal_gaps = sum(section.grid.get_internal_gap_height() for section in sections)
    # Clamp oversized sections so tiles keep a touch-friendly shape instead of stretching to fill the full panel.
    fit_row_height = max(0.0, (rect.height - self._top_padding - total_title_height - total_section_gaps - total_internal_gaps) / total_rows)
    if fit_row_height >= self._min_row_height:
      return min(fit_row_height, self._max_row_height)
    return fit_row_height

  def _draw_section_title(self, rect: rl.Rectangle, title: str):
    title_text = title.upper()
    spacing = round(self._title_font_size * 0.08)
    size = measure_text_cached(self._font_title, title_text, self._title_font_size, spacing=spacing)
    text_y = rect.y + (rect.height - size.y) / 2
    text_pos = rl.Vector2(round(rect.x), round(text_y))
    rl.draw_text_ex(self._font_title, title_text, rl.Vector2(text_pos.x + 1, text_pos.y + 1), self._title_font_size, spacing, rl.Color(0, 0, 0, 90))
    rl.draw_text_ex(self._font_title, title_text, text_pos, self._title_font_size, spacing, rl.Color(255, 255, 255, 215))

    line_x = rect.x + size.x + SPACING.lg
    line_w = rect.width - (line_x - rect.x)
    if line_w <= 0:
      return
    line_y = int(rect.y + rect.height / 2)
    rl.draw_rectangle(int(line_x), line_y, int(line_w), 2, rl.Color(255, 255, 255, 36))

  def _render(self, rect: rl.Rectangle):
    self.set_rect(rect)
    sections = [section for section in self._sections if section.grid.tiles]
    if not sections:
      return

    content_rect = self._content_rect(rect)
    row_height = self._compute_row_height(content_rect, sections)
    if row_height <= 0:
      return

    y = content_rect.y + self._top_padding
    for index, section in enumerate(sections):
      if section.title:
        title_rect = rl.Rectangle(content_rect.x, y, content_rect.width, self._title_height)
        self._draw_section_title(title_rect, section.title)
        y += self._title_height + self._title_gap

      active_grid_height = (section.grid.get_row_count() * row_height) + section.grid.get_internal_gap_height()
      section.grid.render(rl.Rectangle(content_rect.x, y, content_rect.width, active_grid_height))
      y += self._section_band_height(section, row_height)

      if index < len(sections) - 1:
        y += self._section_gap
