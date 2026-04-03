def should_show_forget_button(network=None, *, is_saved: bool = False, is_connected: bool = False) -> bool:
  if network is not None:
    return bool(network.is_saved or network.is_connected)

  return bool(is_saved or is_connected)
