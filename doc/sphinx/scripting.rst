Script entry point
^^^^^^^^^^^^^^^^^^
  with get_script_context('cli') as ctx:
    do_stuff_here()

  * The argument to get_script_context() could influence things like a prompt()
    function. In a cli context it would use stdin/stdout for communication, in
    a gui context a standard QDialog would be shown.

  * The context manager must know if it is the only user of the application
    infrastructure or not. The decision about whether the application needs to
    shutdown or not depends on it.

* Argument parsing (sys.argv for cli, faked sys.argv for the gui)
* Print, prompt (yes/no style but with additional choices), sleep
* mesycontrol protocol specific: has_write_access(), acquire_write_access(),
  release_write_access(), ensure_write_access()
* Connecting/disconnecting to/from MRCs, listing connections
* Setup and config loading, traversing of a loaded setup, (re-)applying setup
  Configs, saving of setups
* Cached and non-cached access to device memory
* Blocking and non-blocking access to devices. Blocking access is only blocking
  from the scripts perspective. It may not block the process completely!
* MRC standard commands: rc on/off, read, write, scanbus
* Device specific functionality (mhv4.enable_all_channels(),
  mhv4.disable_all_channels() mhv4.enable_channels(0,2,3),
  mhv4.is_channel_enabled(0))
  This should be available in a blocking and in a non-blocking way.

Other extension points for the application
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* generic plugin system with the ability for the plugin to register for certain
  application wide events
* device profiles as plugins
* device subclasses as plugins
* device panels as plugins
* script execution in a dedicated thread. This will cause trouble if Qt GUI
  functionality is to be used from within the script!
* low prio: support for languages other than python
