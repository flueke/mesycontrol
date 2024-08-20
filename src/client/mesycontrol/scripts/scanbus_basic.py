#!/usr/bin/env python

from mesycontrol.script import script_runner_run

# The main() function is also loaded an called by mesycontrol_script_runner.
# The standalone() function is the entry point for the generated script in
# pyproject.toml.

def main(ctx, mrc, args):
    for bus in range(2):
        scanbusResult = mrc.scanbus(bus)

        for addr, entry in enumerate(scanbusResult):
            if entry.idc:
                print(f"{bus=}, {addr=}: found device with idc={entry.idc}, rc={entry.rc}", end='')
                if entry.conflict:
                    print(", address conflict detected!", end='')
                print()

if __name__ == "__main__":
    script_runner_run(main)
