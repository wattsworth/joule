#!/bin/bash
# Mock systemctl script

# Log the full command to a file
echo "systemctl $@" >> /tmp/systemctl.log

# Return a success status (or customize as needed)
exit 0
