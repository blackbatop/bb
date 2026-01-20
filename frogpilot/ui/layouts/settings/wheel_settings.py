from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.confirm_dialog import DialogResult
from openpilot.system.ui.widgets.list_view import ListItem, ButtonAction, ITEM_TEXT_VALUE_COLOR, TextAction
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.frogpilot.common.frogpilot_variables import update_frogpilot_toggles

# Button function mappings
BUTTON_FUNCTIONS = {
  0: "No Action",
  3: "Pause Steering",
}

LONGITUDINAL_FUNCTIONS = {
  1: "Change \"Personality Profile\"",
  2: "Force openpilot to Coast",
  4: "Pause Acceleration/Braking",
  5: "Toggle \"Experimental Mode\" On/Off",
  6: "Toggle \"Traffic Mode\" On/Off",
}

# Button parameter configurations
WHEEL_TOGGLES = [
  ("DistanceButtonControl", "Distance Button", "<b>Action performed when the \"Distance\" button is pressed.</b>"),
  ("LongDistanceButtonControl", "Distance Button (Long Press)", "<b>Action performed when the \"Distance\" button is pressed for more than 0.5 seconds.</b>"),
  ("VeryLongDistanceButtonControl", "Distance Button (Very Long Press)", "<b>Action performed when the \"Distance\" button is pressed for more than 2.5 seconds.</b>"),
  ("LKASButtonControl", "LKAS Button", "<b>Action performed when the \"LKAS\" button is pressed.</b>"),
]


class FrogPilotWheelPanel(Widget):
  def __init__(self):
    super().__init__()

    self._params = Params()
    self._toggles = {}
    self._tuning_level = 0

    # Car capabilities
    self._has_openpilot_longitudinal = False
    self._is_subaru = False
    self._lkas_allowed_for_aol = False

    # Pending dialog action tracking
    self._pending_action = None  # "select_function"
    self._pending_param = None

    self._build_panel()

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def _build_panel(self):
    items = []

    for param, title, desc in WHEEL_TOGGLES:
      control = ListItem(
        title=title,
        description=desc,
        action_item=ButtonAction(
          text="SELECT",
          callback=lambda p=param: self._on_button_click(p),
        ),
      )

      # Store reference for updating value display
      self._toggles[param] = control
      items.append(control)

    self._scroller = Scroller(items, line_separator=True, spacing=0)

  def _get_function_name(self, param: str) -> str:
    """Get the display name for the currently selected function."""
    value = self._params.get_int(param)

    # Check both base and longitudinal functions
    all_functions = {**BUTTON_FUNCTIONS}
    if self._has_openpilot_longitudinal:
      all_functions.update(LONGITUDINAL_FUNCTIONS)

    return all_functions.get(value, "No Action")

  def _on_button_click(self, param: str):
    """Handle button click to open function selection dialog."""
    # Build available functions list
    functions = dict(BUTTON_FUNCTIONS)
    if self._has_openpilot_longitudinal:
      functions.update(LONGITUDINAL_FUNCTIONS)

    # Get current selection
    current_value = self._params.get_int(param)
    current_name = functions.get(current_value, "No Action")

    # Show selection dialog
    self._pending_action = "select_function"
    self._pending_param = param
    gui_app.set_modal_overlay(MultiOptionDialog(
      "Select a function to assign to this button",
      list(functions.values()),
      current_name,
    ))

  def handle_dialog_result(self, result: DialogResult, selection: str = ""):
    """Handle dialog results for pending actions."""
    action = self._pending_action
    param = self._pending_param
    self._pending_action = None
    self._pending_param = None

    if action == "select_function":
      if result != DialogResult.CONFIRM or not selection:
        return

      # Find the function ID for the selected name
      all_functions = {**BUTTON_FUNCTIONS, **LONGITUDINAL_FUNCTIONS}
      function_id = None
      for fid, name in all_functions.items():
        if name == selection:
          function_id = fid
          break

      if function_id is not None and param:
        self._params.put_int(param, function_id)
        update_frogpilot_toggles()

  def _load_car_capabilities(self):
    """Load car capabilities from frogpilot variables."""
    try:
      from openpilot.frogpilot.common.frogpilot_variables import get_frogpilot_toggles
      toggles = get_frogpilot_toggles()

      self._has_openpilot_longitudinal = getattr(toggles, "has_openpilot_longitudinal", False)
      self._is_subaru = getattr(toggles, "is_subaru", False)
      self._lkas_allowed_for_aol = getattr(toggles, "lkas_allowed_for_aol", False)
    except Exception:
      pass

  def _update_toggles(self):
    self._tuning_level = self._params.get_int("TuningLevel") or 0
    self._load_car_capabilities()

    # LKAS button visibility
    lkas_visible = True
    if self._is_subaru:
      lkas_visible = False
    elif self._lkas_allowed_for_aol:
      aol_enabled = self._params.get_bool("AlwaysOnLateral")
      aol_lkas = self._params.get_bool("AlwaysOnLateralLKAS")
      if aol_enabled and aol_lkas:
        lkas_visible = False

    lkas_control = self._toggles.get("LKASButtonControl")
    if lkas_control and hasattr(lkas_control, "set_visible"):
      lkas_control.set_visible(lkas_visible)

  def show_event(self):
    super().show_event()
    self._scroller.show_event()
    self._load_car_capabilities()
    self._update_toggles()

  def _render(self, rect):
    self._scroller.render(rect)
