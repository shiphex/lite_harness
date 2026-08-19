# Domain Overlay: Embedded / Real-Time / Robotics

Apply when code touches RTOS/Linux RT, drivers, control loops, hardware interfaces, sensors, actuators, robotics middleware, or physical side effects.

Check:

- deadline, WCET, jitter, and scheduling assumptions;
- ISR/thread/task boundaries;
- blocking calls in real-time paths;
- dynamic allocation in deterministic paths;
- lock duration and priority inversion;
- shared-buffer ownership;
- watchdog and recovery;
- stack/heap/memory bounds;
- sensor timestamps and stale data;
- units, signs, coordinate frames, scaling, saturation, overflow;
- actuator/GPIO/PWM/CAN/EtherCAT safety limits;
- startup, shutdown, emergency stop, and degraded mode;
- power/battery/thermal/communication fault behavior;
- simulation/HIL evidence before physical activation.

Raise severity when uncertainty can cause unsafe physical behavior.

For control code, verify:

- sample period assumptions;
- saturation/anti-windup;
- sensor/actuator latency;
- frame transforms;
- numerical precision;
- behavior when measurements disappear or become stale.
