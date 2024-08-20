from mesycontrol.script import script_runner_run
import scanbus
import scanbus_basic
import auto_poll_parameters

def scanbus_main():
    script_runner_run(scanbus.main)

def scanbus_basic_main():
    script_runner_run(scanbus_basic.main)

def auto_poll_parameters_main():
    script_runner_run(auto_poll_parameters.main)
