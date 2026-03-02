from device import ModbusDevice


class SwitchDevice(ModbusDevice):
    device_type = "Switch"
    default_role = "switch"
    default_instance = 40

    def device_init_late(self):
        super().device_init_late()

    def _add_switchable_output(
        self,
        index,
        name,
        type,
        valid_types,
        writeable=True,
        default_value=0,
        custom_name=None,
        group=None,
        visible_by_default=1,
        output_range=(0, 100),
        labels=[],
        debug=False,
    ):
        """Helper to add a switchable output to D-Bus

        Args:
            index: Output index (0, 1, 2, etc.)
            name: Display name for the output
            type: Type of input (0=button, 1=relay, etc.)
            valid_types: Valid types bitmask
            writeable: Whether output can be controlled (False for read-only status)
            custom_name: Optional custom name for Settings
            visible_by_default: Whether the output is visible by default in the UI
            output_range: Tuple (min, max) for numeric inputs
        """
        if debug:
            writeable = True  # Always allow writing in debug mode
        base = f"/SwitchableOutput/{index}"

        assert self._dbus is not None, "D-Bus not initialized"
        assert self._dbus.add_path is not None, "D-Bus not initialized" # The type checker was annoying me

        # All outputs have these common paths
        if writeable:
            self._dbus.add_path(
                f"{base}/State",
                default_value,
                writeable=writeable,
                onchangecallback=self._on_output_changed if writeable else None,
            )
        self._dbus.add_path(f"{base}/Measurement", 1, writeable=True)
        self._dbus.add_path(f"{base}/Name", name, writeable=True)
        self._dbus.add_path(f"{base}/Status", 0x09, writeable=True)
        self._dbus.add_path(
            f"{base}/Settings/ShowUIControl", visible_by_default, writeable=True
        )
        self._dbus.add_path(f"{base}/Settings/Type", type, writeable=debug)
        self._dbus.add_path(f"{base}/Settings/ValidTypes", valid_types, writeable=debug)

        #self._dbus.add_path(f"/Alarms/Tripped", 0, writeable=True)

        if custom_name:
            self._dbus.add_path(
                f"{base}/Settings/CustomName", custom_name, writeable=debug
            )
            self._dbus.add_path(f"{base}/Settings/Labels", 0, writeable=True)

        if group:
            self._dbus.add_path(f"{base}/Settings/Group", group, writeable=debug)

        # Specific paths for dropdown inputs
        # The dimming value is the index in the labels list
        if type == 6:  # Dropdown
            self._dbus.add_path(
                f"{base}/Settings/DimmingMin",
                0,
                writeable=debug,
            )
            self._dbus.add_path(
                f"{base}/Settings/DimmingMax",
                len(labels) - 1,
                writeable=debug,
            )
            self._dbus.add_path(
                f"{base}/Settings/Labels",
                labels,
                writeable=debug,
            )
            self._dbus.add_path(
                f"{base}/Dimming",
                default_value,
                writeable=True,
                onchangecallback=self._on_output_changed if writeable else None,
            )

        # Specific paths for numeric inputs
        # the dimming value is the numeric value that was input
        if type == 8:  # Numeric input
            self._dbus.add_path(
                f"{base}/Dimming",
                default_value,
                writeable=True,
                onchangecallback=self._on_output_changed if writeable else None,
            )
            self._dbus.add_path(
                f"{base}/Settings/DimmingMin", output_range[0], writeable=debug
            )
            self._dbus.add_path(
                f"{base}/Settings/DimmingMax", output_range[1], writeable=debug
            )

    def _set_output_visibility(self, output_num, visible):
        """Helper to show/hide switchable outputs"""
        assert self._dbus is not None, "D-Bus not initialized"
        assert self._dbus.add_path is not None, "D-Bus not initialized" # The type checker was annoying me

        path = f"/SwitchableOutput/{output_num}/Settings/ShowUIControl"
        if path in self._dbus:
            self._dbus[path] = 1 if visible else 0

    def _set_labels(self, output_num, labels):
        """Helper to set the labels for a dropdown output"""
        assert self._dbus is not None, "D-Bus not initialized"
        assert self._dbus.add_path is not None, "D-Bus not initialized" # The type checker was annoying me

        path = f"/SwitchableOutput/{output_num}/Settings/Labels"
        if path in self._dbus:
            self._dbus[path] = labels

        path = f"/SwitchableOutput/{output_num}/Settings/DimmingMax"
        if path in self._dbus:
            self._dbus[path] = len(labels) - 1
