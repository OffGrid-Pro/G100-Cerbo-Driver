#!/bin/bash

# Post-hook script to run after files have been extracted.
echo "Running post-hook script..."

# Change permissions to make the scripts executable
echo "Setting permissions for install script..."
chmod +x /data/venus-data/offgridpro/install.sh

# Run the install script
echo "Running install script..."
/data/venus-data/offgridpro/install.sh

# Add the install script to rc.local to survive firmware updates
echo "Ensuring install script is added to rc.local..."
if ! grep -q "/data/venus-data/offgridpro/install.sh" /data/rc.local; then
    echo "/data/venus-data/offgridpro/install.sh" >> /data/rc.local
    chmod 755 /data/rc.local
fi
echo "Post-hook script completed."