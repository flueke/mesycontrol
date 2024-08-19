import functools
import importlib.util
import logging
import secrets
import signal
import string
import sys
from mesycontrol.script import get_script_context

# Source for gensym() and load_module(): https://medium.com/@david.bonn.2010/dynamic-loading-of-python-code-2617c04e5f3f
def gensym(length=32, prefix="gensym_"):
    """
    generates a fairly unique symbol, used to make a module name,
    used as a helper function for load_module

    :return: generated symbol
    """
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    symbol = "".join([secrets.choice(alphabet) for i in range(length)])

    return prefix + symbol


def load_module(source, module_name=None):
    """
    reads file source and loads it as a module

    :param source: file to load
    :param module_name: name of module to register in sys.modules
    :return: loaded module
    """

    if module_name is None:
        module_name = gensym()

    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module

def script_runner_main():
    if len(sys.argv) < 3:
        print(f"""Usage: <mrc-url> <script-py> [--debug] [script-args]

Generic runner for mesycontrol scripts. The script-py file must contain a main()
function taking a context object and an optional list of arguments:

  def main(ctx: mesycontrol.script.ScriptContext, mrc: script.MRCWrapper, args: List[str]):
        mrcs = ctx.get_all_mrcs()
        # Interact with the MRCs here.

Accepted mrc-url schemes:
  - For serial connections:
      <serial_port>@<baud> | serial://<serial_port>[@<baud>]
      e.g. /dev/ttyUSB0, /dev/ttyUSB0@115200
  - For TCP connections (serial server connected to an MRC1):
      <host>:<port>
      tcp://<host>[:<port=4001>]
  - For connections to a mesycontrol server:
      mc://<host>[:<port=23000>]
"""
    )
        sys.exit(0)


    mrcUrl = sys.argv[1]
    scriptFile = sys.argv[2]
    scriptArgs = sys.argv[3:]
    doDebug = "--debug" in sys.argv

    print(f"{mrcUrl=}, {scriptFile=}, {scriptArgs=}")

    try:
        scriptModule = load_module(scriptFile)
        scriptMain = scriptModule.main
    except Exception as e:
        print(f"Failed to load script file {scriptFile}: {e}")
        sys.exit(1)

    with get_script_context(logging.DEBUG if doDebug else logging.INFO) as ctx:
        def signal_handler(ctx, signum, frame):
            ctx.quit = True

        signal.signal(signal.SIGINT, functools.partial(signal_handler, ctx))

        mrc = ctx.make_mrc(mrcUrl)
        connectResult = mrc.connectMrc()
        if not connectResult:
            print(f"Failed to connect to mrc {mrcUrl}, {connectResult=}")
            sys.exit(1)

        print(f"Connected to mrc {mrcUrl=}, executing 'main' from {scriptFile}")
        scriptMain(ctx, mrc, scriptArgs)

if __name__ == "__main__":
    script_runner_main()
