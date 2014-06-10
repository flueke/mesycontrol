from mesycontrol.script import *
from mesycontrol import config_xml, setup

def print_progress(cur, tot):
    # \r moves the cursor to the start of the line. The comma at the very end
    # suppresses the newline from the print statement.
    print "\rBuilding setup (step %d/%d)" % (cur, tot),

if len(sys.argv) < 3:
    print "Usage: %s <setup_output_file> <connection_url1> [<connection_urlN>...]" % sys.argv[0]
    print """Writes a XML setup file containing the current state of all
    connected devices to the given output filename."""
    sys.exit(1)

outfile_name    = sys.argv[1]
connection_urls = sys.argv[2:]

with get_script_context() as ctx:
    source_filter = util.SourceFilter()
    log_handler   = logging.StreamHandler(sys.stderr)
    log_handler.setLevel(logging.WARNING)
    log_handler.addFilter(source_filter)
    log_handler.setFormatter(logging.Formatter(fmt='[%(name)s.%(levelname)s] %(message)s'))
    logging.getLogger().addHandler(log_handler)

    setup_builder = setup.SetupBuilder()
    setup_builder.progress_changed.connect(print_progress)

    for url in connection_urls:
        print "Connecting to %s" % url
        conn = ctx.make_connection(url=url)
        conn.connect()
        setup_builder.add_mrc(conn.mrc)

        source_filter.add_qobject_tree(conn.mrc._wrapped)

    source_filter.add_qobject_tree(setup_builder)

    # Run the builder and get the resulting Config object
    setup_config = setup_builder()

    print "\nWriting setup to %s" % outfile_name

    with open(outfile_name, 'w') as outfile:
        config_xml.write_file(setup_config, outfile)
