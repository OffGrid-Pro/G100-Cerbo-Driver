#!/bin/bash
# Install script for OffGridPro G100 Modbus device integration
echo "Running OffGridPro G100 install script..."

# Temporarily make the rootfs writable
echo "Remounting root filesystem as read-write..."
mount -o remount,rw /

# Symlink our files to /opt/victronenergy/dbus-modbus-client/
echo "Creating symlinks for OGP_G100.py and switch_device.py..."
ln -sf /data/venus-data/offgridpro/OGP_G100.py /opt/victronenergy/dbus-modbus-client/
ln -sf /data/venus-data/offgridpro/switch_device.py /opt/victronenergy/dbus-modbus-client/

# Add "import OGP_G100" to /opt/victronenergy/dbus-modbus-client/dbus-modbus-client.py if not already present
echo "Ensuring OGP_G100 is imported in dbus-modbus-client.py..."
if ! grep -q "import OGP_G100" /opt/victronenergy/dbus-modbus-client/dbus-modbus-client.py; then
    # Insert the import statement after "import carlo_gavazzi"
    sed -i '/^import carlo_gavazzi$/a import OGP_G100' /opt/victronenergy/dbus-modbus-client/dbus-modbus-client.py
fi

# Add an entry for "USB_Serial" to the serial-starter.rules file if not already present
echo "Ensuring USB_Serial entry is present in serial-starter.rules..."
if ! grep -q "USB_Serial" /etc/udev/rules.d/serial-starter.rules ; then
cat >> /etc/udev/rules.d/serial-starter.rules <<EOF

# OffGridPro G100: Add an entry for a generic RS485 adapter incase not using the Victron one
ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_MODEL}=="USB_Serial", ENV{VE_SERVICE}="modbus"
EOF
fi

# Remount rootfs as read-only
echo "Remounting root filesystem as read-only..."
mount -o remount,ro /

echo "OffGridPro G100 install script completed."