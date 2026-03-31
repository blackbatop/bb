import pyray as rl
from msgq.visionipc import VisionStreamType
from openpilot.common.params import Params
from openpilot.selfdrive.ui import UI_BORDER_SIZE
from openpilot.selfdrive.ui.onroad.augmented_road_view import AugmentedRoadView, BORDER_COLORS
from openpilot.selfdrive.ui.onroad.starpilot.personality_button import PersonalityButton, BTN_SIZE
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus

AOL_COLOR = rl.Color(10, 186, 181, 255)


class StarPilotOnroadView(AugmentedRoadView):
  def __init__(self, stream_type: VisionStreamType = VisionStreamType.VISION_STREAM_ROAD):
    super().__init__(stream_type)
    self._params = Params()

    self._personality_button = PersonalityButton()

  def _render(self, rect: rl.Rectangle):
    super()._render(rect)

    if not ui_state.started:
      return

    self._render_overlays()

  def _render_overlays(self):
    self._position_personality_button()
    self._personality_button.render()

  def _position_personality_button(self):
    dm = self.driver_state_renderer
    toggle_on = self._params.get_bool("OnroadDistanceButton")

    if not dm.is_visible or not toggle_on:
      self._personality_button.set_visible(False)
      return

    self._personality_button.set_visible(
      lambda: ui_state.started and ui_state.has_longitudinal_control
    )

    y = dm.position_y - BTN_SIZE / 2
    if dm.is_rhd:
      x = dm.position_x - BTN_SIZE * 2
    else:
      x = dm.position_x + BTN_SIZE

    self._personality_button.set_position(x, y)

  def _draw_border(self, rect: rl.Rectangle):
    rl.draw_rectangle_lines_ex(rect, UI_BORDER_SIZE, rl.BLACK)
    border_rect = rl.Rectangle(rect.x + UI_BORDER_SIZE, rect.y + UI_BORDER_SIZE,
                                rect.width - 2 * UI_BORDER_SIZE, rect.height - 2 * UI_BORDER_SIZE)
    border_color = AOL_COLOR if ui_state.always_on_lateral_active else BORDER_COLORS.get(ui_state.status, BORDER_COLORS[UIStatus.DISENGAGED])
    rl.draw_rectangle_rounded_lines_ex(border_rect, 0.12, 10, UI_BORDER_SIZE, border_color)

  def _handle_mouse_press(self, _):
    if self._personality_button.is_interacting:
      return
    super()._handle_mouse_press(_)
