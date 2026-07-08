import dbus
import dbus.mainloop.glib
import logging
import os
import sys
from gi.repository import GLib

sys.path.insert(0, '/opt/victronenergy/dbus-modbus-client')
from vedbus import VeDbusService, VeDbusItemImport  # noqa: E402  (path must be set first)

log = logging.getLogger(__name__)

PLACEHOLDER_SVC = 'com.victronenergy.switch.ogp_g100_placeholder'
REAL_PREFIX = 'com.victronenergy.switch.ogp_'

PRODUCT_NAME_WAITING = 'OGP G100 CLS [Not Connected]'
DEVICE_INSTANCE = 40
PRODUCT_ID = 0xB0FF


def _get_bus():
    if 'DBUS_SESSION_BUS_ADDRESS' in os.environ:
        return dbus.SessionBus()
    return dbus.SystemBus()


def _is_real_device(name):
    """Return True if name is an OGP real device (not our own placeholder)."""
    return name.startswith(REAL_PREFIX) and name != PLACEHOLDER_SVC


class OGPPlaceholder:
    _GRID_PATHS = (
        '/Ac/Grid/L1/Power',
        '/Ac/Grid/L2/Power',
        '/Ac/Grid/L3/Power',
    )

    def __init__(self, bus):
        self.bus = bus
        self._svc = None
        self._real_present = False
        self._grid_powers = dict.fromkeys(self._GRID_PATHS)  # None = unknown
        self._grid_watchers = []

    def _register(self):
        if self._svc is not None:
            return

        svc = VeDbusService(PLACEHOLDER_SVC, self.bus, register=False)
        svc.add_mandatory_paths(
            processname='ogp-placeholder',
            processversion='1.0',
            connection='Waiting for device',
            deviceinstance=DEVICE_INSTANCE,
            productid=PRODUCT_ID,
            productname=PRODUCT_NAME_WAITING,
            firmwareversion=0,
            hardwareversion=0,
            connected=0,
        )
        svc.register()

        self._svc = svc
        log.info('Placeholder registered as %s', PLACEHOLDER_SVC)

    def _unregister(self):
        if self._svc is None:
            return
        self._svc.__del__()
        self._svc = None
        log.info('Placeholder unregistered')

    def _setup_grid_watchers(self):
        """Subscribe to system grid power paths and seed initial values."""
        for path in self._GRID_PATHS:
            watcher = VeDbusItemImport(
                self.bus,
                'com.victronenergy.system',
                path,
                eventCallback=self._on_grid_changed,
            )
            if watcher.exists:
                v = watcher.get_value()
                self._grid_powers[path] = int(v) if v is not None else None
            self._grid_watchers.append(watcher)
        self._update_product_name()

    def _on_grid_changed(self, item, path, value):
        if value is None:
            self._grid_powers[path] = None
        else:
            try:
                self._grid_powers[path] = int(value.get('Value', 0))
            except (TypeError, ValueError):
                self._grid_powers[path] = None
        self._update_product_name()

    def _update_product_name(self):
        if self._svc is None:
            return
        known = [v for v in self._grid_powers.values() if v is not None]
        if known:
            total = sum(known)
            name = f'OGP G100 CLS [Not Connected \u00b7 Grid: {total}W]'
        else:
            name = PRODUCT_NAME_WAITING
        self._svc['/ProductName'] = name

    def _on_name_owner_changed(self, name, old_owner, new_owner):
        if not _is_real_device(name):
            return

        if new_owner and not self._real_present:
            log.info('Real device appeared (%s) — stepping aside', name)
            self._real_present = True
            self._unregister()

        elif not new_owner and self._real_present:
            log.info('Real device gone (%s) — re-registering placeholder', name)
            self._real_present = False
            self._register()

    def run(self):
        # Check whether the real device is already on the bus at startup so
        # we don't briefly flash a placeholder entry on connect.
        self._real_present = any(
            _is_real_device(n) for n in self.bus.list_names()
        )

        if not self._real_present:
            self._register()

        self.bus.add_signal_receiver(
            self._on_name_owner_changed,
            signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',
            path='/org/freedesktop/DBus',
        )

        self._setup_grid_watchers()

        log.info(
            'OGP placeholder running (real device already present: %s)',
            self._real_present,
        )
        GLib.MainLoop().run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    OGPPlaceholder(_get_bus()).run()
