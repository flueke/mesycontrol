from mesycontrol.script import script_runner_run

# Do lazy imports so that scripts with missing external dependencies (e.g.
# influxdb) do not cause other scripts to fail.

def auto_poll_parameters_main():
    from .auto_poll_parameters import main
    script_runner_run(main)

def auto_poll_to_influxdb_main():
    from .auto_poll_to_influxdb import main
    script_runner_run(main)

def scanbus_main():
    from .scanbus import main
    script_runner_run(main)

def scanbus_basic_main():
    from .scanbus_basic import main
    script_runner_run(main)
