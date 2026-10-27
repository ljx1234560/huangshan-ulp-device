# Required computer permissions

Full administrator or unrestricted filesystem access is not required for normal development.

Required capabilities:

1. Read and write this repository.
2. Read the external SiFli-SDK and execute its compiler, Python environment, SCons, and `sftool`.
3. Query Windows serial devices through CIM/WMI.
4. Open the selected CH340 COM port for flashing, logging, and commands.
5. Use network access only when fetching SDK updates or dependencies.

Administrator access is only expected when Windows needs a USB-serial driver installed, a protected system setting changed, or another process/service prevents normal serial access. Keep approvals scoped to the exact command or directory instead of enabling permanent full-computer access.

