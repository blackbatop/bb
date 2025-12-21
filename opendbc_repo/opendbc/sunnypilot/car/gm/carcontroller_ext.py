"""
Minimal GM carcontroller extensions for branches without pedal/interceptor support.
"""


class GasInterceptorCarController:
  def __init__(self, CP, CP_SP):
    # No-op initializer; kept for interface compatibility
    self.frame = 0
    self.CP = CP
    self.CP_SP = CP_SP

  def extend_with_interceptor(self, CC, CS, actuators, can_sends):
    # Stubbed out for branches without pedal/interceptor support
    return
