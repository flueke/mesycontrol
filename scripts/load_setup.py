from mesycontrol.command import *
from mesycontrol.mrc_command import *
from mesycontrol.script import *
from mesycontrol import config_xml
from mesycontrol import setup

def print_progress(cur, tot):
    print "Loading setup (step %d/%d)" % (cur, tot)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s <setup_file>" % sys.argv[0]
        sys.exit(1)

    with get_script_context() as ctx:
        print "Loading setup from %s" % sys.argv[1]
        cfg = config_xml.parse_file(sys.argv[1])

        print ("Setup contents: %d connections, %d device configs, %d device descriptions" %
                (len(cfg.mrc_connections), len(cfg.device_configs), len(cfg.device_descriptions)))

        setup_loader = setup.SetupLoader(cfg)
        setup_loader.progress_changed.connect(print_progress)
        setup_loader.exec_()

        print "Current connections and bus data:"
        for conn in ctx.app_model.mrc_connections:
            print " "*2, conn.get_info()
            mrc = MRCWrapper(conn.mrc_model)
            for i in range(2):
                print " "*4, mrc[i]

        if setup_loader.has_failed():
            print "Error loading setup" # TODO: get error response or whatever caused the error
            sys.exit(1)
        else:
            print "Setup loaded"
            sys.exit(0)

