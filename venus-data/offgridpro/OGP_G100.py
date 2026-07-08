import logging
import device
import switch_device
import probe
from gi.repository import GLib
from register import *

# Absolutely misusing every part of the victron ui here, but as long as the correct info comes across it's fine.
# if I had more time I'd make a proper victron ui component for this device but with guiv2 it wont work very well lol

log = logging.getLogger()

class Reg_serial(Reg, str):
    """
    Serial is the mac address of the device, stored as 3 16-bit registers.
    """
    def __init__(self, base, name):
        super().__init__(base, 3, name)

    def decode(self, values):
        v = '%04X%04X%04X' % (values[0], values[1], values[2])
        return self.update(v)
    
class Reg_ver(Reg, str):
    """
    Versions are stored as uint16, in format major.minor.patch, where minor and patch are 2 digits.
    ex: 0x283C -> 10300 -> 1.03.00 or 0x4E85 -> 20101 -> 2.01.01
    """
    def __init__(self, base, name):
        super().__init__(base, 1, name)

    def decode(self, values):
        v = values[0]
        major = v // 10000
        minor = (v % 10000) // 100
        patch = v % 100
        return self.update('%d.%02d.%02d' % (major, minor, patch))
    
class Reg_state_with_callback(Reg_u16):
    """State register that triggers output updates on change"""
    def __init__(self, base, name, device_obj):
        super().__init__(base, name, write=True)
        self.device_obj = device_obj
    
    def decode(self, values):
        result = super().decode(values)
        # Trigger output updates when state changes
        if result is not None and hasattr(self.device_obj, '_update_outputs_from_state'):
            self.device_obj._update_outputs_from_state(values[0])
        return result


class G100_CLS_BASE(device.CustomName, switch_device.SwitchDevice):
    vendor_id = 'ogp'
    vendor_name = 'OffGrid Pro'
    productid = 0xB0FF
    productname = 'OGP G100 CLS'
    min_timeout = 1.0

    #nr_phases = 1

    def device_init(self):
        # Read hardware, firmware and serial from text registers
        self.info_regs = [
            Reg_ver(0x0000, '/HardwareVersion'),
            Reg_ver(0x0010, '/FirmwareVersion'),
            Reg_serial(0x0020, '/Serial'),
        ]

        self.read_info()

        regs = [
            Reg_state_with_callback(0x0040, '/State', self),
            Reg_u16(0x0050, '/SwitchableOutput/1/State'),
            Reg_u16(0x0051, '/SwitchableOutput/2/State'),
            Reg_s32b(0x2000, '/MaxExportLimit'),
            Reg_s32b(0x2002, '/MaxImportLimit'),
        ]

        self.data_regs = regs

    def device_init_late(self):
        super().device_init_late()
    
        from vedbus import VeDbusItemImport

        assert self._dbus is not None, "D-Bus not initialized"
        assert self._dbus.dbusconn is not None, "D-Bus not initialized"

        self.grid_changed_L1 = VeDbusItemImport(
            self._dbus.dbusconn,
            "com.victronenergy.system",
            "/Ac/Grid/L1/Power",
            eventCallback=self.system_grid_changed,
        ) # Value is in16 -327680 to 327670

        self.grid_changed_L1 = VeDbusItemImport(
            self._dbus.dbusconn,
            "com.victronenergy.system",
            "/Ac/Grid/L1/Power",
            eventCallback=self.system_grid_changed,
        ) # Value is in16 -327680 to 327670

        self.grid_changed_L2 = VeDbusItemImport(
            self._dbus.dbusconn,
            "com.victronenergy.system",
            "/Ac/Grid/L2/Power",
            eventCallback=self.system_grid_changed,
        ) # Value is in16 -327680 to 327670

        self.grid_changed_L3 = VeDbusItemImport(
            self._dbus.dbusconn,
            "com.victronenergy.system",
            "/Ac/Grid/L3/Power",
            eventCallback=self.system_grid_changed
        ) # Value is in16 -327680 to 327670

        self.time = VeDbusItemImport(
            self._dbus.dbusconn,
            "com.victronenergy.platform",
            "/Device/Time",
            eventCallback=self.system_time_changed,
        ) # Value is in seconds since epoch

        if self.time.exists:
            initial_time = self.time.get_value()
            self.system_time_changed(self.time, "/Device/Time", initial_time)

    def _on_output_changed(self, path, value):
        """Handle switchable output state changes"""
        return True

    def system_grid_changed(self, item, path, value):
        """Write grid power"""
        try:
            if value is None:
                val = 0
            else:
                val = int(value.get("Value", 0))
                
                # Convert int32 to 2 uint16 registers (high word, low word)
                # Pack as signed 32-bit int, unpack as 2 unsigned 16-bit ints
                bytes_val = struct.pack('>i', val)  # '>i' = big-endian signed int32
                high, low = struct.unpack('>HH', bytes_val)  # '>HH' = 2 big-endian uint16
                
                if "L1" in path:
                    self.write_modbus(0x1050, [high, low])
                elif "L2" in path:
                    self.write_modbus(0x1052, [high, low])
                elif "L3" in path:
                    self.write_modbus(0x1054, [high, low])
                logging.debug("Wrote grid power %d to G100 (high=0x%04X, low=0x%04X)", val, high, low)
            
        except Exception as e:
            log.error("Error writing grid power to G100: %s", e)
            self.write_modbus(0x1050, [0, 0])
            self.write_modbus(0x1052, [0, 0])
            self.write_modbus(0x1054, [0, 0])

    def system_time_changed(self, item, path, value):
        """Write system time to device"""
        try:
            if value is None:
                val = 0
            else:
                val = int(value)
                # Convert int32 to 2 uint16 registers (high word, low word)
                bytes_val = struct.pack('>i', val)  # '>i' = big-endian signed int32
                high, low = struct.unpack('>HH', bytes_val)  # '>HH' = 2 big-endian uint16
                
                self.write_modbus(0x2004, [high, low])
                logging.debug("Wrote system time %d to G100 (high=0x%04X, low=0x%04X)", val, high, low)
            
        except Exception as e:
            log.error("Error writing system time to G100: %s", e)
            self.write_modbus(0x2004, [0, 0])

    def _update_outputs_from_state(self, state):
        """Update switchable output statuses based on device state"""
        assert self._dbus is not None, "D-Bus not initialized"

        try:
            if state == 0x100:
                # Normal operation
                if hasattr(self, '_dbus'):
                    self._dbus['/SwitchableOutput/0/Status'] = 0x09
                    self._dbus['/SwitchableOutput/1/Status'] = 0x80
                    self._dbus['/SwitchableOutput/2/Status'] = 0x80
                    log.debug("Set auxiliary outputs to off state")
            elif state == 0x103:
                # Warning state
                if hasattr(self, '_dbus'):
                    self._dbus['/SwitchableOutput/0/Status'] = 0x09
                    self._dbus['/SwitchableOutput/1/Status'] = 0x80 #! In the latest update victron have changed the mapping of the state codes so over import / export now dont show in ui :/
                    self._dbus['/SwitchableOutput/2/Status'] = 0x80 #! Check git history for old code, was "channel tripped" but that now maps to "off"
                    log.debug("Set auxiliary outputs to warning state")
            elif state == 0x104:
                # Alarm state
                if hasattr(self, '_dbus'):
                    self._dbus['/SwitchableOutput/0/Status'] = 0x82
                    self._dbus['/SwitchableOutput/1/Status'] = 0x82
                    self._dbus['/SwitchableOutput/2/Status'] = 0x82
                    log.debug("Set auxiliary outputs to alarm state")
            elif state == 0x105:
                # State 4
                if hasattr(self, '_dbus'):
                    self._dbus['/SwitchableOutput/0/Status'] = 0x08
                    self._dbus['/SwitchableOutput/1/Status'] = 0x08
                    self._dbus['/SwitchableOutput/2/Status'] = 0x08
                    log.debug("Set auxiliary outputs to disabled state")
        except Exception as e:
            log.error("Error updating outputs from state: %s", e)

    def dbus_write_register(self, reg, path, val):
        super().dbus_write_register(reg, path, val)
        self.sched_reinit()



# region Default
class G100_CLS(G100_CLS_BASE):
    def device_init_late(self):
        super().device_init_late()
        self._add_switchable_output(0, "Reset System", type=0, valid_types=0x1, writeable=True)
        self._add_switchable_output(1, "Auxiliary Output 1", type=1, valid_types=0x2, writeable=False)
        self._add_switchable_output(2, "Auxiliary Output 2", type=1, valid_types=0x2, writeable=False)
        # occasionally read the register to force the device out of config mode if it is stuck there for some reason
        GLib.timeout_add(2000, self._send_config_exit)

    def _on_output_changed(self, path, value):
        """Handle switchable output state changes"""
        if '/SwitchableOutput/0/State' in path and value == 1:
            self._handle_reset_button()
        return True

    def _send_config_exit(self):
        """if for whatever reason the device is still in config mode, kick it out by reading the id register"""
        try:
            self.read_modbus(0x0030, 1)
            log.info("Read 0x0030 to force G100 out of config mode")
        except Exception as e:
            log.error("Error reading config-exit register: %s", e)
        return False  # Do not repeat

    def _handle_reset_button(self):
        """Send reset command to device"""
        try:
            self.write_modbus(0x1060, [0x0001])
            log.info("Reset command sent to G100")
        except Exception as e:
            log.error("Error sending reset command: %s", e)
# endregion

models = {
    0xFAAC: {
        'model': 'CLS',
        'handler': G100_CLS,
    },
}

probe.add_handler(probe.ModelRegister(Reg_u16(0x0030), models,
                                      methods=['rtu'],
                                      units=[1],
                                      rates=[19200]))