# Application

Product state machines, use cases, and RT-Thread application threads belong here.

`velapet_core.c` is the portable offline domain core. It owns the canonical pet,
daily-task, experience, streak, and skin-unlock rules without depending on
RT-Thread, LVGL, a filesystem, wall-clock functions, or heap allocation. Platform
code supplies a monotonically increasing local calendar `day_id`; persistence
and UI adapters will be added separately.

