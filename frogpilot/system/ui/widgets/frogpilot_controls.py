import math
import os
import pyray as rl

from collections.abc import Callable

from openpilot.common.params import Params
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.widgets.label import Label
from openpilot.system.ui.widgets.list_view import ITEM_DESC_FONT_SIZE, ITEM_DESC_TEXT_COLOR
from openpilot.system.ui.widgets.toggle import Toggle

__all__ = [
  "CONTROL_HEIGHT",
  "DEFAULT_BUTTON_HEIGHT",
  "DEFAULT_BUTTON_WIDTH",
  "FROGPILOT_VALUE_COLOR",
  "ITEM_SPACING",
  "SEPARATOR_MARGIN",
  "FrogPilotButtonControl",
  "FrogPilotButtonsControl",
  "FrogPilotButtonToggleControl",
  "FrogPilotConfirmationDialog",
  "FrogPilotDualParamValueControl",
  "FrogPilotListWidget",
  "FrogPilotManageControl",
  "FrogPilotParamValueButtonControl",
  "FrogPilotParamValueControl",
  "GifAnimation",
  "clear_gif",
  "load_gif",
  "load_image",
  "load_texture_cached",
  "open_descriptions",
]

CONTROL_HEIGHT = 120
DEFAULT_BUTTON_HEIGHT = 100
DEFAULT_BUTTON_WIDTH = 225
FROGPILOT_VALUE_COLOR = rl.Color(224, 232, 121, 255)
ITEM_SPACING = 25
SEPARATOR_MARGIN = 40

_gif_cache: dict[str, "GifAnimation"] = {}
_texture_cache: dict[str, rl.Texture] = {}


class GifAnimation:
  def __init__(self, gif_path: str, size: tuple[int, int] | None = None):
    self._current_frame = 0
    self._frame_count = 0
    self._frame_delay = 0.1
    self._frames: list[rl.Texture] = []
    self._last_update = 0.0
    self._loaded = False
    self._path = gif_path
    self._running = False
    self._size = size

    self._load_gif()

  def _load_gif(self) -> None:
    if not os.path.exists(self._path):
      return

    try:
      frame_count = rl.ffi.new("int *")
      image = rl.load_image_anim(self._path.encode(), frame_count)
      self._frame_count = frame_count[0]

      if self._frame_count <= 0:
        rl.unload_image(image)
        return

      frame_height = image.height // self._frame_count
      for i in range(self._frame_count):
        frame_rect = rl.Rectangle(0, i * frame_height, image.width, frame_height)
        frame_image = rl.image_from_image(image, frame_rect)

        if self._size:
          rl.image_resize(rl.ffi.addressof(frame_image), self._size[0], self._size[1])

        texture = rl.load_texture_from_image(frame_image)
        self._frames.append(texture)
        rl.unload_image(frame_image)

      rl.unload_image(image)
      self._loaded = True
    except Exception:
      self._loaded = False

  @property
  def file_name(self) -> str:
    return self._path

  @property
  def is_loaded(self) -> bool:
    return self._loaded and len(self._frames) > 0

  @property
  def is_running(self) -> bool:
    return self._running

  @property
  def scaled_size(self) -> tuple[int, int] | None:
    return self._size

  def get_current_texture(self) -> rl.Texture | None:
    if not self.is_loaded:
      return None
    return self._frames[self._current_frame]

  def render(self, x: int, y: int, tint: rl.Color = rl.WHITE) -> None:
    self.update()
    texture = self.get_current_texture()
    if texture:
      rl.draw_texture(texture, x, y, tint)

  def set_scaled_size(self, size: tuple[int, int]) -> None:
    if self._size == size:
      return
    self._size = size

  def start(self) -> None:
    self._running = True
    self._last_update = rl.get_time()

  def stop(self) -> None:
    self._running = False

  def unload(self) -> None:
    for texture in self._frames:
      rl.unload_texture(texture)
    self._frames.clear()
    self._loaded = False

  def update(self) -> None:
    if not self._running or not self.is_loaded:
      return

    current_time = rl.get_time()
    if current_time - self._last_update >= self._frame_delay:
      self._current_frame = (self._current_frame + 1) % self._frame_count
      self._last_update = current_time


def clear_gif(gif: GifAnimation | None) -> None:
  if gif is None:
    return

  gif.stop()
  gif.unload()


def load_gif(gif_path: str, size: tuple[int, int], use_cache: bool = True) -> GifAnimation | None:
  if not gif_path or not os.path.exists(gif_path):
    return None

  cache_key = f"{gif_path}_{size[0]}x{size[1]}"

  if use_cache and cache_key in _gif_cache:
    cached = _gif_cache[cache_key]
    if cached.is_loaded:
      if not cached.is_running:
        cached.start()
      return cached

  gif = GifAnimation(gif_path, size)
  if not gif.is_loaded:
    return None

  gif.start()

  if use_cache:
    _gif_cache[cache_key] = gif

  return gif


def load_image(base_path: str, size: tuple[int, int]) -> tuple[rl.Texture | None, GifAnimation | None]:
  gif_path = base_path + ".gif"
  if os.path.exists(gif_path):
    gif = load_gif(gif_path, size)
    return (None, gif)

  png_path = base_path + ".png"
  texture = load_texture_cached(png_path, size[0], size[1])
  return (texture, None)


def load_texture_cached(path: str, width: int = 0, height: int = 0) -> rl.Texture | None:
  if not path:
    return None

  cache_key = f"{path}_{width}_{height}"
  if cache_key in _texture_cache:
    return _texture_cache[cache_key]

  actual_path = path
  if not os.path.exists(path):
    for ext in [".png", ".gif", ".jpg", ".jpeg"]:
      test_path = path + ext
      if os.path.exists(test_path):
        actual_path = test_path
        break
    else:
      return None

  texture = gui_app.texture(actual_path, width, height) if width > 0 and height > 0 else rl.load_texture(actual_path)
  _texture_cache[cache_key] = texture
  return texture


def open_descriptions(force_open: bool, toggles: dict) -> None:
  if force_open:
    for key, toggle in toggles.items():
      if key != "CESpeed" and hasattr(toggle, "show_description"):
        toggle.show_description()


class FrogPilotButtonControl(Widget):
  def __init__(self,
               param: str,
               title: str,
               description: str,
               icon: str = "",
               button_texts: list[str] = None,
               checkable: bool = False,
               exclusive: bool = False,
               minimum_button_width: int = DEFAULT_BUTTON_WIDTH):
    super().__init__()

    self._button_checked: list[bool] = []
    self._button_enabled: list[bool] = []
    self._buttons: list[Button] = []
    self._checkable = checkable
    self._click_callback: Callable[[int], None] | None = None
    self._description = description
    self._disabled_click_callback: Callable[[int], None] | None = None
    self._exclusive = exclusive
    self._minimum_button_width = minimum_button_width
    self._param_key = param
    self._params = Params()

    self._desc_label = Label(description, font_size=ITEM_DESC_FONT_SIZE,
                             text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
                             text_color=ITEM_DESC_TEXT_COLOR)
    self._title_label = Label(title, font_size=50, font_weight=FontWeight.MEDIUM,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._toggle = Toggle(initial_state=self._params.get_bool(param),
                          callback=self._on_toggle_changed)

    button_texts = button_texts or []
    for i, text in enumerate(button_texts):
      btn = Button(text, click_callback=lambda idx=i: self._on_button_click(idx),
                   button_style=ButtonStyle.LIST_ACTION)
      self._buttons.append(btn)
      self._button_checked.append(False)
      self._button_enabled.append(True)

  def _on_button_click(self, button_id: int) -> None:
    if not self._button_enabled[button_id]:
      if self._disabled_click_callback:
        self._disabled_click_callback(button_id)
      return

    if self._checkable:
      if self._exclusive:
        for i in range(len(self._button_checked)):
          self._button_checked[i] = (i == button_id)
      else:
        self._button_checked[button_id] = not self._button_checked[button_id]

    if self._click_callback:
      self._click_callback(button_id)

  def _on_toggle_changed(self, state: bool) -> None:
    self._params.put_bool(self._param_key, state)
    self.refresh()

  def _render(self, rect: rl.Rectangle) -> None:
    desc_height = ITEM_DESC_FONT_SIZE if self._description else 0
    title_height = 50
    toggle_width = 160

    visible_buttons = [(i, btn) for i, btn in enumerate(self._buttons) if btn.is_visible]
    total_button_width = sum(self._minimum_button_width for _ in visible_buttons) + 10 * max(0, len(visible_buttons) - 1)

    text_width = rect.width - total_button_width - toggle_width - 60

    title_rect = rl.Rectangle(rect.x + 20, rect.y + 10, text_width, title_height)
    self._title_label.render(title_rect)

    if self._description:
      desc_rect = rl.Rectangle(rect.x + 20, rect.y + 10 + title_height + 5, text_width, desc_height)
      self._desc_label.render(desc_rect)

    if visible_buttons:
      button_x = rect.x + text_width + 30
      button_y = rect.y + (rect.height - DEFAULT_BUTTON_HEIGHT) // 2

      toggle_state = self._toggle.get_state()
      for i, btn in visible_buttons:
        btn.set_enabled(self._button_enabled[i] and toggle_state)

        if self._checkable and self._button_checked[i]:
          btn.set_button_style(ButtonStyle.PRIMARY)
        else:
          btn.set_button_style(ButtonStyle.LIST_ACTION)

        btn_rect = rl.Rectangle(button_x, button_y, self._minimum_button_width, DEFAULT_BUTTON_HEIGHT)
        btn.render(btn_rect)
        button_x += self._minimum_button_width + 10

    toggle_x = rect.x + rect.width - toggle_width - 20
    toggle_y = rect.y + (rect.height - 80) // 2
    self._toggle.render(rl.Rectangle(toggle_x, toggle_y, toggle_width, 80))

  def clear_checked_buttons(self) -> None:
    for i in range(len(self._button_checked)):
      self._button_checked[i] = False

  def refresh(self) -> None:
    state = self._params.get_bool(self._param_key)
    self._toggle.set_state(state)

    for i in range(len(self._button_enabled)):
      self._button_enabled[i] = state

  def set_checked_button(self, button_id: int) -> None:
    if 0 <= button_id < len(self._button_checked):
      self._button_checked[button_id] = True

  def set_click_callback(self, callback: Callable[[int], None]) -> None:
    self._click_callback = callback

  def set_disabled_click_callback(self, callback: Callable[[int], None]) -> None:
    self._disabled_click_callback = callback

  def set_enabled(self, enable: bool) -> None:
    for i in range(len(self._button_enabled)):
      self._button_enabled[i] = enable

  def set_enabled_buttons(self, button_id: int, enable: bool) -> None:
    if 0 <= button_id < len(self._button_enabled):
      self._button_enabled[button_id] = enable

  def set_text(self, button_id: int, text: str) -> None:
    if 0 <= button_id < len(self._buttons):
      self._buttons[button_id].set_text(text)

  def set_visible_button(self, button_id: int, visible: bool) -> None:
    if 0 <= button_id < len(self._buttons):
      self._buttons[button_id].set_visible(visible)

  def show_event(self) -> None:
    self.refresh()


class FrogPilotButtonsControl(Widget):
  def __init__(self,
               title: str,
               description: str,
               icon: str = "",
               button_texts: list[str] = None,
               checkable: bool = False,
               exclusive: bool = True,
               minimum_button_width: int = DEFAULT_BUTTON_WIDTH):
    super().__init__()

    self._button_checked: list[bool] = []
    self._button_enabled: list[bool] = []
    self._buttons: list[Button] = []
    self._checkable = checkable
    self._click_callback: Callable[[int], None] | None = None
    self._description = description
    self._disabled_click_callback: Callable[[int], None] | None = None
    self._exclusive = exclusive
    self._minimum_button_width = minimum_button_width

    self._desc_label = Label(description, font_size=ITEM_DESC_FONT_SIZE,
                             text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
                             text_color=ITEM_DESC_TEXT_COLOR)
    self._title_label = Label(title, font_size=50, font_weight=FontWeight.MEDIUM,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    button_texts = button_texts or []
    for i, text in enumerate(button_texts):
      btn = Button(text, click_callback=lambda idx=i: self._on_button_click(idx),
                   button_style=ButtonStyle.LIST_ACTION)
      self._buttons.append(btn)
      self._button_checked.append(False)
      self._button_enabled.append(True)

  def _on_button_click(self, button_id: int) -> None:
    if not self._button_enabled[button_id]:
      if self._disabled_click_callback:
        self._disabled_click_callback(button_id)
      return

    if self._checkable:
      if self._exclusive:
        for i in range(len(self._button_checked)):
          self._button_checked[i] = (i == button_id)
      else:
        self._button_checked[button_id] = not self._button_checked[button_id]

    if self._click_callback:
      self._click_callback(button_id)

  def _render(self, rect: rl.Rectangle) -> None:
    desc_height = ITEM_DESC_FONT_SIZE if self._description else 0
    text_width = rect.width * 0.5
    title_height = 50

    title_rect = rl.Rectangle(rect.x + 20, rect.y + 10, text_width, title_height)
    self._title_label.render(title_rect)

    if self._description:
      desc_rect = rl.Rectangle(rect.x + 20, rect.y + 10 + title_height + 5, text_width, desc_height)
      self._desc_label.render(desc_rect)

    visible_buttons = [(i, btn) for i, btn in enumerate(self._buttons) if btn.is_visible]
    if visible_buttons:
      total_button_width = sum(self._minimum_button_width for _ in visible_buttons) + 10 * (len(visible_buttons) - 1)
      button_x = rect.x + rect.width - total_button_width - 20
      button_y = rect.y + (rect.height - DEFAULT_BUTTON_HEIGHT) // 2

      for i, btn in visible_buttons:
        btn.set_enabled(self._button_enabled[i])

        if self._checkable and self._button_checked[i]:
          btn.set_button_style(ButtonStyle.PRIMARY)
        else:
          btn.set_button_style(ButtonStyle.LIST_ACTION)

        btn_rect = rl.Rectangle(button_x, button_y, self._minimum_button_width, DEFAULT_BUTTON_HEIGHT)
        btn.render(btn_rect)
        button_x += self._minimum_button_width + 10

  def clear_checked_buttons(self) -> None:
    for i in range(len(self._button_checked)):
      self._button_checked[i] = False

  def set_checked_button(self, button_id: int) -> None:
    if 0 <= button_id < len(self._button_checked):
      self._button_checked[button_id] = True

  def set_click_callback(self, callback: Callable[[int], None]) -> None:
    self._click_callback = callback

  def set_disabled_click_callback(self, callback: Callable[[int], None]) -> None:
    self._disabled_click_callback = callback

  def set_enabled(self, enable: bool) -> None:
    for i in range(len(self._button_enabled)):
      self._button_enabled[i] = enable

  def set_enabled_buttons(self, button_id: int, enable: bool) -> None:
    if 0 <= button_id < len(self._button_enabled):
      self._button_enabled[button_id] = enable

  def set_text(self, button_id: int, text: str) -> None:
    if 0 <= button_id < len(self._buttons):
      self._buttons[button_id].set_text(text)

  def set_visible_button(self, button_id: int, visible: bool) -> None:
    if 0 <= button_id < len(self._buttons):
      self._buttons[button_id].set_visible(visible)


class FrogPilotButtonToggleControl(FrogPilotButtonControl):
  def __init__(self,
               param: str,
               title: str,
               description: str,
               icon: str = "",
               button_params: list[str] = None,
               button_texts: list[str] = None,
               exclusive: bool = False,
               minimum_button_width: int = DEFAULT_BUTTON_WIDTH):
    super().__init__(param, title, description, icon, button_texts, True, exclusive, minimum_button_width)

    self._button_params = button_params or []

    for i, bp in enumerate(self._button_params):
      if i < len(self._button_checked):
        self._button_checked[i] = self._params.get_bool(bp)

  def _on_button_click(self, button_id: int) -> None:
    if not self._button_enabled[button_id]:
      if self._disabled_click_callback:
        self._disabled_click_callback(button_id)
      return

    if button_id < len(self._button_params):
      new_state = not self._button_checked[button_id]
      self._button_checked[button_id] = new_state
      self._params.put_bool(self._button_params[button_id], new_state)

    if self._click_callback:
      self._click_callback(button_id)

  def refresh(self) -> None:
    super().refresh()

    for i, bp in enumerate(self._button_params):
      if i < len(self._button_checked):
        self._button_checked[i] = self._params.get_bool(bp)


class FrogPilotConfirmationDialog(ConfirmDialog):
  def __init__(self, prompt_text: str, confirm_text: str, cancel_text: str, rich: bool = False):
    super().__init__(prompt_text, confirm_text, cancel_text, rich)

  @staticmethod
  def create_toggle_reboot() -> "FrogPilotConfirmationDialog":
    return FrogPilotConfirmationDialog(
      "Reboot required to take effect.",
      "Reboot Now",
      "Reboot Later"
    )

  @staticmethod
  def create_yesorno(prompt_text: str) -> "FrogPilotConfirmationDialog":
    return FrogPilotConfirmationDialog(prompt_text, "Yes", "No")

  @staticmethod
  def toggle_reboot(parent=None) -> bool:
    return False

  @staticmethod
  def yesorno(prompt_text: str, parent=None) -> bool:
    return False


class FrogPilotDualParamValueControl(Widget):
  def __init__(self, control1: "FrogPilotParamValueControl", control2: "FrogPilotParamValueControl"):
    super().__init__()
    self._control1 = control1
    self._control2 = control2

  def _render(self, rect: rl.Rectangle) -> None:
    half_width = rect.width // 2 - 5

    control1_rect = rl.Rectangle(rect.x, rect.y, half_width, rect.height)
    control2_rect = rl.Rectangle(rect.x + half_width + 10, rect.y, half_width, rect.height)

    self._control1.render(control1_rect)
    self._control2.render(control2_rect)

  def refresh(self) -> None:
    self._control1.refresh()
    self._control2.refresh()

  def update_control(self, min_value: float, max_value: float, value_labels: dict[float, str] = None) -> None:
    self._control1.update_control(min_value, max_value, value_labels)
    self._control2.update_control(min_value, max_value, value_labels)


class FrogPilotListWidget(Widget):
  def __init__(self, spacing: int = ITEM_SPACING):
    super().__init__()
    self._items: list[Widget] = []
    self._spacing = spacing

  def _render(self, rect: rl.Rectangle) -> None:
    if not self._items:
      return

    current_y = rect.y
    visible_items = [item for item in self._items if item.is_visible]

    for i, item in enumerate(visible_items):
      item_height = item.rect.height if item.rect.height > 0 else CONTROL_HEIGHT
      item_rect = rl.Rectangle(rect.x, current_y, rect.width, item_height)

      item.render(item_rect)

      if i < len(visible_items) - 1:
        separator_y = current_y + item_height + self._spacing // 2
        rl.draw_line(
          int(rect.x + SEPARATOR_MARGIN),
          int(separator_y),
          int(rect.x + rect.width - SEPARATOR_MARGIN),
          int(separator_y),
          ITEM_DESC_TEXT_COLOR
        )

      current_y += item_height + self._spacing

  def add_item(self, widget: Widget, expanding: bool = False) -> None:
    self._items.append(widget)

  def clear(self) -> None:
    self._items.clear()

  def insert_item(self, index: int, widget: Widget, expanding: bool = False) -> None:
    self._items.insert(index, widget)

  def set_spacing(self, spacing: int) -> None:
    self._spacing = spacing


class FrogPilotManageControl(Widget):
  def __init__(self, param: str, title: str, description: str, icon: str = ""):
    super().__init__()

    self._description = description
    self._manage_callback: Callable[[], None] | None = None
    self._manage_visible = True
    self._param_key = param
    self._params = Params()

    self._desc_label = Label(description, font_size=ITEM_DESC_FONT_SIZE,
                             text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
                             text_color=ITEM_DESC_TEXT_COLOR)
    self._manage_button = Button("MANAGE", click_callback=self._on_manage_clicked,
                                 button_style=ButtonStyle.LIST_ACTION)
    self._title_label = Label(title, font_size=50, font_weight=FontWeight.MEDIUM,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._toggle = Toggle(initial_state=self._params.get_bool(param),
                          callback=self._on_toggle_changed)

  def _on_manage_clicked(self) -> None:
    if self._manage_callback:
      self._manage_callback()

  def _on_toggle_changed(self, state: bool) -> None:
    self._params.put_bool(self._param_key, state)
    self.refresh()

  def _render(self, rect: rl.Rectangle) -> None:
    desc_height = ITEM_DESC_FONT_SIZE if self._description else 0
    manage_width = 150 if self._manage_visible else 0
    title_height = 50
    toggle_width = 160

    text_width = rect.width - toggle_width - manage_width - 60

    title_rect = rl.Rectangle(rect.x + 20, rect.y + 10, text_width, title_height)
    self._title_label.render(title_rect)

    if self._description:
      desc_rect = rl.Rectangle(rect.x + 20, rect.y + 10 + title_height + 5, text_width, desc_height)
      self._desc_label.render(desc_rect)

    if self._manage_visible:
      manage_x = rect.x + text_width + 30
      manage_y = rect.y + (rect.height - DEFAULT_BUTTON_HEIGHT) // 2
      self._manage_button.render(rl.Rectangle(manage_x, manage_y, manage_width, DEFAULT_BUTTON_HEIGHT))

    toggle_x = rect.x + rect.width - toggle_width - 20
    toggle_y = rect.y + (rect.height - 80) // 2
    self._toggle.render(rl.Rectangle(toggle_x, toggle_y, toggle_width, 80))

  def refresh(self) -> None:
    state = self._params.get_bool(self._param_key)
    self._toggle.set_state(state)
    self._manage_button.set_enabled(state)

  def set_manage_callback(self, callback: Callable[[], None]) -> None:
    self._manage_callback = callback

  def set_manage_visibility(self, visible: bool) -> None:
    self._manage_visible = visible

  def show_event(self) -> None:
    self.refresh()


class FrogPilotParamValueButtonControl(Widget):
  def __init__(self,
               param: str,
               title: str,
               description: str,
               icon: str = "",
               min_value: float = 0,
               max_value: float = 100,
               label: str = "",
               value_labels: dict[float, str] = None,
               interval: float = 1.0,
               fast_increase: bool = False,
               button_params: list[str] = None,
               button_texts: list[str] = None,
               left_button: bool = False,
               checkable: bool = True,
               minimum_button_width: int = DEFAULT_BUTTON_WIDTH):
    super().__init__()

    self._button_checked: list[bool] = []
    self._button_click_callback: Callable[[int], None] | None = None
    self._button_enabled: list[bool] = []
    self._button_params = button_params or []
    self._buttons: list[Button] = []
    self._checkable = checkable
    self._decrement_repeating = False
    self._description = description
    self._display_warning = False
    self._factor = 10 ** math.ceil(-math.log10(interval)) if interval > 0 else 1
    self._fast_increase = fast_increase
    self._increment_repeating = False
    self._interval = interval
    self._label_suffix = label
    self._label_width = 200
    self._last_action_time = 0.0
    self._left_button = left_button
    self._max_value = max_value
    self._min_value = min_value
    self._minimum_button_width = minimum_button_width
    self._param_key = param
    self._params = Params()
    self._value_changed_callback: Callable[[float], None] | None = None
    self._value_labels = value_labels or {}
    self._warning_shown = False

    self._value = self._read_param_value()
    self._previous_value = self._value

    self._decrement_button = Button("-", click_callback=self._on_decrement,
                                    font_size=50, button_style=ButtonStyle.LIST_ACTION)
    self._desc_label = Label(description, font_size=ITEM_DESC_FONT_SIZE,
                             text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
                             text_color=ITEM_DESC_TEXT_COLOR)
    self._increment_button = Button("+", click_callback=self._on_increment,
                                    font_size=50, button_style=ButtonStyle.LIST_ACTION)
    self._title_label = Label(title, font_size=50, font_weight=FontWeight.MEDIUM,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._value_label = Label(self._format_value(), font_size=50,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_RIGHT,
                              text_color=FROGPILOT_VALUE_COLOR)

    button_texts = button_texts or []
    for i, text in enumerate(button_texts):
      checked = checkable and i < len(self._button_params) and self._params.get_bool(self._button_params[i])
      btn = Button(text, click_callback=lambda idx=i: self._on_button_click(idx),
                   button_style=ButtonStyle.PRIMARY if checked else ButtonStyle.LIST_ACTION)
      self._buttons.append(btn)
      self._button_checked.append(checked)
      self._button_enabled.append(True)

  def _format_value(self) -> str:
    for val, label in self._value_labels.items():
      if round(val * self._factor) == round(self._value * self._factor):
        return label

    if self._interval >= 1:
      return f"{int(self._value)}{self._label_suffix}"
    else:
      decimals = max(0, int(math.ceil(-math.log10(self._interval))))
      return f"{self._value:.{decimals}f}{self._label_suffix}"

  def _on_button_click(self, button_id: int) -> None:
    if self._checkable and button_id < len(self._button_params):
      new_state = not self._button_checked[button_id]
      self._button_checked[button_id] = new_state
      self._params.put_bool(self._button_params[button_id], new_state)

      self._buttons[button_id].set_button_style(
        ButtonStyle.PRIMARY if new_state else ButtonStyle.LIST_ACTION
      )

    if self._button_click_callback:
      self._button_click_callback(button_id)

  def _on_decrement(self) -> None:
    if self._display_warning and not self._warning_shown:
      self._show_warning()

    current_time = rl.get_time()
    if current_time - self._last_action_time > 0.65:
      self._decrement_repeating = False

    delta = self._interval * 5 if self._decrement_repeating and self._fast_increase else self._interval
    self._value = max(self._value - delta, self._min_value)
    self._update_value()

    if round(self._value / self._interval) % 5 == 0:
      self._decrement_repeating = True

    self._last_action_time = current_time

  def _on_increment(self) -> None:
    if self._display_warning and not self._warning_shown:
      self._show_warning()

    current_time = rl.get_time()
    if current_time - self._last_action_time > 0.65:
      self._increment_repeating = False

    delta = self._interval * 5 if self._increment_repeating and self._fast_increase else self._interval
    self._value = min(self._value + delta, self._max_value)
    self._update_value()

    if round(self._value / self._interval) % 5 == 0:
      self._increment_repeating = True

    self._last_action_time = current_time

  def _read_param_value(self) -> float:
    try:
      return float(self._params.get_int(self._param_key))
    except (ValueError, TypeError):
      try:
        return self._params.get_float(self._param_key)
      except (ValueError, TypeError):
        return self._min_value

  def _render(self, rect: rl.Rectangle) -> None:
    button_size = 100
    total_btn_width = sum(self._minimum_button_width for _ in self._buttons) + 10 * max(0, len(self._buttons) - 1)

    if self._left_button:
      btn_start_x = rect.x + 20
      value_start_x = btn_start_x + total_btn_width + 20
    else:
      value_start_x = rect.x + rect.width - button_size * 2 - self._label_width - 40
      btn_start_x = rect.x + rect.width - total_btn_width - button_size * 2 - 60

    text_width = value_start_x - rect.x - 40 if not self._left_button else rect.width - total_btn_width - self._label_width - button_size * 2 - 100

    desc_height = ITEM_DESC_FONT_SIZE if self._description else 0
    title_height = 50

    title_rect = rl.Rectangle(rect.x + 20, rect.y + 10, text_width, title_height)
    self._title_label.render(title_rect)

    if self._description:
      desc_rect = rl.Rectangle(rect.x + 20, rect.y + 10 + title_height + 5, text_width, desc_height)
      self._desc_label.render(desc_rect)

    button_y = rect.y + (rect.height - DEFAULT_BUTTON_HEIGHT) // 2
    current_btn_x = btn_start_x

    for i, btn in enumerate(self._buttons):
      btn.set_enabled(self._button_enabled[i])
      btn.render(rl.Rectangle(current_btn_x, button_y, self._minimum_button_width, DEFAULT_BUTTON_HEIGHT))
      current_btn_x += self._minimum_button_width + 10

    value_x = rect.x + rect.width - button_size * 2 - self._label_width - 40
    value_y = rect.y + (rect.height - 50) // 2
    self._value_label.render(rl.Rectangle(value_x, value_y, self._label_width, 50))

    button_y = rect.y + (rect.height - button_size) // 2

    dec_x = rect.x + rect.width - button_size * 2 - 30
    self._decrement_button.render(rl.Rectangle(dec_x, button_y, button_size, button_size))

    inc_x = rect.x + rect.width - button_size - 20
    self._increment_button.render(rl.Rectangle(inc_x, button_y, button_size, button_size))

  def _show_warning(self) -> None:
    self._warning_shown = True

  def _update_value(self) -> None:
    self._value = round(self._value * self._factor) / self._factor
    self._value_label.set_text(self._format_value())

    self._decrement_button.set_enabled(self._value > self._min_value)
    self._increment_button.set_enabled(self._value < self._max_value)

    if self._value_changed_callback:
      self._value_changed_callback(self._value)

  def _write_param_value(self) -> None:
    if self._value == self._previous_value:
      return

    if self._interval >= 1 and self._interval == int(self._interval):
      self._params.put_int(self._param_key, int(self._value))
    else:
      self._params.put_float(self._param_key, self._value)

    self._previous_value = self._value

  def hide_event(self) -> None:
    self._warning_shown = False
    self._write_param_value()

  def refresh(self) -> None:
    self._value = self._read_param_value()
    self._value = max(self._min_value, min(self._max_value, self._value))
    self._previous_value = self._value
    self._update_value()
    self._write_param_value()

    if self._checkable:
      for i, bp in enumerate(self._button_params):
        if i < len(self._button_checked):
          checked = self._params.get_bool(bp)
          self._button_checked[i] = checked
          self._buttons[i].set_button_style(
            ButtonStyle.PRIMARY if checked else ButtonStyle.LIST_ACTION
          )

  def set_button_click_callback(self, callback: Callable[[int], None]) -> None:
    self._button_click_callback = callback

  def set_enabled_buttons(self, button_id: int, enable: bool) -> None:
    if 0 <= button_id < len(self._button_enabled):
      self._button_enabled[button_id] = enable

  def set_value_changed_callback(self, callback: Callable[[float], None]) -> None:
    self._value_changed_callback = callback

  def set_warning(self, warning: str) -> None:
    self._display_warning = True

  def show_event(self) -> None:
    self.refresh()

  def update_control(self, min_value: float, max_value: float, value_labels: dict[float, str] = None) -> None:
    self._min_value = min_value
    self._max_value = max_value
    if value_labels is not None:
      self._value_labels = value_labels
    self.refresh()


class FrogPilotParamValueControl(Widget):
  def __init__(self,
               param: str,
               title: str,
               description: str,
               icon: str = "",
               min_value: float = 0,
               max_value: float = 100,
               label: str = "",
               value_labels: dict[float, str] = None,
               interval: float = 1.0,
               fast_increase: bool = False,
               label_width: int = 350):
    super().__init__()

    self._decrement_repeating = False
    self._description = description
    self._display_warning = False
    self._factor = 10 ** math.ceil(-math.log10(interval)) if interval > 0 else 1
    self._fast_increase = fast_increase
    self._increment_repeating = False
    self._interval = interval
    self._label_suffix = label
    self._label_width = label_width
    self._last_action_time = 0.0
    self._max_value = max_value
    self._min_value = min_value
    self._param_key = param
    self._params = Params()
    self._value_changed_callback: Callable[[float], None] | None = None
    self._value_labels = value_labels or {}
    self._warning_shown = False

    self._value = self._read_param_value()
    self._previous_value = self._value

    self._decrement_button = Button("-", click_callback=self._on_decrement,
                                    font_size=50, button_style=ButtonStyle.LIST_ACTION)
    self._desc_label = Label(description, font_size=ITEM_DESC_FONT_SIZE,
                             text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
                             text_color=ITEM_DESC_TEXT_COLOR)
    self._increment_button = Button("+", click_callback=self._on_increment,
                                    font_size=50, button_style=ButtonStyle.LIST_ACTION)
    self._title_label = Label(title, font_size=50, font_weight=FontWeight.MEDIUM,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._value_label = Label(self._format_value(), font_size=50,
                              text_alignment=rl.GuiTextAlignment.TEXT_ALIGN_RIGHT,
                              text_color=FROGPILOT_VALUE_COLOR)

  def _format_value(self) -> str:
    for val, label in self._value_labels.items():
      if round(val * self._factor) == round(self._value * self._factor):
        return label

    if self._interval >= 1:
      return f"{int(self._value)}{self._label_suffix}"
    else:
      decimals = max(0, int(math.ceil(-math.log10(self._interval))))
      return f"{self._value:.{decimals}f}{self._label_suffix}"

  def _on_decrement(self) -> None:
    if self._display_warning and not self._warning_shown:
      self._show_warning()

    current_time = rl.get_time()
    if current_time - self._last_action_time > 0.65:
      self._decrement_repeating = False

    delta = self._interval * 5 if self._decrement_repeating and self._fast_increase else self._interval
    self._value = max(self._value - delta, self._min_value)
    self._update_value()

    if round(self._value / self._interval) % 5 == 0:
      self._decrement_repeating = True

    self._last_action_time = current_time

  def _on_increment(self) -> None:
    if self._display_warning and not self._warning_shown:
      self._show_warning()

    current_time = rl.get_time()
    if current_time - self._last_action_time > 0.65:
      self._increment_repeating = False

    delta = self._interval * 5 if self._increment_repeating and self._fast_increase else self._interval
    self._value = min(self._value + delta, self._max_value)
    self._update_value()

    if round(self._value / self._interval) % 5 == 0:
      self._increment_repeating = True

    self._last_action_time = current_time

  def _read_param_value(self) -> float:
    try:
      return float(self._params.get_int(self._param_key))
    except (ValueError, TypeError):
      try:
        return self._params.get_float(self._param_key)
      except (ValueError, TypeError):
        return self._min_value

  def _render(self, rect: rl.Rectangle) -> None:
    button_size = 100
    desc_height = ITEM_DESC_FONT_SIZE if self._description else 0
    text_width = rect.width - self._label_width - button_size * 2 - 60
    title_height = 50
    value_width = self._label_width

    title_rect = rl.Rectangle(rect.x + 20, rect.y + 10, text_width, title_height)
    self._title_label.render(title_rect)

    if self._description:
      desc_rect = rl.Rectangle(rect.x + 20, rect.y + 10 + title_height + 5, text_width, desc_height)
      self._desc_label.render(desc_rect)

    value_x = rect.x + text_width + 20
    value_y = rect.y + (rect.height - 50) // 2
    self._value_label.render(rl.Rectangle(value_x, value_y, value_width, 50))

    button_y = rect.y + (rect.height - button_size) // 2

    dec_x = rect.x + rect.width - button_size * 2 - 30
    self._decrement_button.render(rl.Rectangle(dec_x, button_y, button_size, button_size))

    inc_x = rect.x + rect.width - button_size - 20
    self._increment_button.render(rl.Rectangle(inc_x, button_y, button_size, button_size))

  def _show_warning(self) -> None:
    self._warning_shown = True

  def _update_value(self) -> None:
    self._value = round(self._value * self._factor) / self._factor
    self._value_label.set_text(self._format_value())

    self._decrement_button.set_enabled(self._value > self._min_value)
    self._increment_button.set_enabled(self._value < self._max_value)

    if self._value_changed_callback:
      self._value_changed_callback(self._value)

  def _write_param_value(self) -> None:
    if self._value == self._previous_value:
      return

    if self._interval >= 1 and self._interval == int(self._interval):
      self._params.put_int(self._param_key, int(self._value))
    else:
      self._params.put_float(self._param_key, self._value)

    self._previous_value = self._value

  def hide_event(self) -> None:
    self._warning_shown = False
    self._write_param_value()

  def refresh(self) -> None:
    self._value = self._read_param_value()
    self._value = max(self._min_value, min(self._max_value, self._value))
    self._previous_value = self._value
    self._update_value()
    self._write_param_value()

  def set_value_changed_callback(self, callback: Callable[[float], None]) -> None:
    self._value_changed_callback = callback

  def set_warning(self, warning: str) -> None:
    self._display_warning = True

  def show_event(self) -> None:
    self.refresh()

  def update_control(self, min_value: float, max_value: float, value_labels: dict[float, str] = None) -> None:
    self._min_value = min_value
    self._max_value = max_value
    if value_labels is not None:
      self._value_labels = value_labels
    self.refresh()
