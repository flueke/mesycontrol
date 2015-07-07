        """Handles the case where the generator yields a Future object.
        The default action is to wait for the future to complete and then send
        the future back into the generator.
        """
        def on_done(f):
            self.arg = f
            QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)

        f.add_done_callback(on_done)
        return True

    def _progress_update(self, progress):
        self.result.set_progress_range(0, progress.total)
        self.result.set_progress(progress.current)
        self.result.set_progress_text(progress.text)

    def _object_yielded(self, obj):
        """Called if the generator yields any object other than Future or
        ProgressUpdate."""
        raise NotImplementedError()

    def _stop_iteration(self):
        """Called on encountering a StopIteration exception. The default is to
        set the result futures value to True."""
        if not self.result.done():
            self.result.set_result(True)

    def _exception(self, e):
        """Called on encountering an exception other than StopIteration.  If
        the exception is an instance of Aborted the result futures value will
        be set to False. Otherwise the exception is reraised with the original
        traceback."""
        if isinstance(e, Aborted):
            self.result.set_result(False)
        else:
            raise e, None, sys.exc_info()[2]

class ProgressUpdate(object):
    __slots__ = ['current', 'total', 'text']

    def __init__(self, current, total, text=str()):
        self.current = current
        self.total   = total
        self.text    = text

    def __iadd__(self, other):
        self.current += other
        return self

    def increment(self, delta=1):
        self += delta
        return self

    def __str__(self):
        if not len(self.text):
            return "%d/%d" % (self.current, self.total)
        return "%d/%d: %s" % (self.current, self.total, self.text)

class SetParameterError(RuntimeError):
    pass

class IDCConflict(RuntimeError):
    pass

class MissingDestinationDevice(RuntimeError):
    def __init__(self, url, bus, dev):
        self.url = url
        self.bus = bus
        self.dev = dev

class MissingDestinationMRC(RuntimeError):
    def __init__(self, url):
        self.url = url

class Aborted(RuntimeError):
    pass

ACTION_SKIP, ACTION_ABORT, ACTION_RETRY = range(3)

def apply_device_config(source, dest, device_profile):
    """Apply device config operation in the form of a generator.
    Yields Futures and ProgressUpdates. Raises StopIteration on completion.
    """

    def check_idcs():
        if source.idc != dest.idc:
            raise IDCConflict(
                    "IDCConflict: mrc=%s, bus=%d, dev=%d, src-idc=%d, dest-idc=%d" %
                    (source.mrc.get_display_url(), source.bus, source.address,
                        source.idc, dest.idc))

        if source.idc != device_profile.idc:
            raise IDCConflict(
                    "IDCConflict: mrc=%s, bus=%d, dev=%d, src-idc=%d, profile-idc=%d" %
                    (source.mrc.get_display_url(), source.bus, source.address,
                        source.idc, device_profile.idc))

    try:
        check_idcs()

        non_criticals   = device_profile.get_non_critical_config_parameters()
        criticals       = device_profile.get_critical_parameters()
        values          = dict()

        # Get available parameters directly from the sources cache. This is
        # mostly to smoothen progress updates as otherwise progress would jump
        # to around 50% instantly if all parameters are in the sources cache.

        for pp in itertools.chain(non_criticals, criticals):
            if source.has_cached_parameter(pp.address):
                values[pp.address] = source.get_cached_parameter(pp.address)

        # number of parameters left to read from source
        total_progress  = (len(non_criticals) + len(criticals)) - len(values)
        # number of parameters to be written to dest
        total_progress += len(non_criticals) + 2 * len(criticals)

        progress      = ProgressUpdate(current=0, total=total_progress)
        progress.text = "Reading from source"

        yield progress

        # Note: The code below executes async operations (get and set
        # parameter) in bursts instead of queueing one request and waiting for
        # its future to complete. This way the devices request queue won't be
        # empty and thus polling won't interfere with our requests.

        futures = list()

        # Read remaining parameters from source.
        for pp in filter(lambda pp: pp.address not in values,
                itertools.chain(non_criticals, criticals)):

            futures.append(source.get_parameter(pp.address))

        for f in futures:
            yield f
            check_idcs()
            r = f.result()

            values[r.address] = r.value

            yield progress.increment()

        if len(criticals):
            progress.text = "Setting critical parameters to safe values"

        futures = list()

        # Set safe values for critical parameters.
        for pp in criticals:
            futures.append(dest.set_parameter(pp.address, pp.safe_value))

        for f in futures:
            f = yield f
            check_idcs()
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        progress.text = "Writing to destination"

        futures = list()

        # Set non-criticals
        for pp in non_criticals:
            value = values[pp.address]
            futures.append(dest.set_parameter(pp.address, value))

        for f in futures:
            f = yield f
            check_idcs()
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        if len(criticals):
            progress.text = "Writing critical parameters to destination"

        futures = list()

        # Finally set criticals to their config values
        for pp in criticals:
            value = values[pp.address]
            futures.append(dest.set_parameter(pp.address, value))

        for f in futures:
            check_idcs()
            f = yield f
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        progress.text = "Config applied successfully"
        yield progress

        raise StopIteration()
    finally:
        pass

def establish_connections(setup, hardware_registry):
    for cfg_mrc in setup:
        hw_mrc = hardware_registry.get_mrc(cfg_mrc.url)

        if hw_mrc is None:
            model_util.add_mrc_connection(hardware_registry=hardware_registry,
                    url=cfg_mrc.url, do_connect=False)

            hw_mrc = hardware_registry.get_mrc(cfg_mrc.url)

        if hw_mrc.is_connecting():
            # Cancel active connection attempts as we need the Future returned
            # by connect().
            yield hw_mrc.disconnect()

        if hw_mrc.is_disconnected():
            action = ACTION_RETRY

            while action == ACTION_RETRY:
                f = yield hw_mrc.connect()

                try:
                    f.result()
                    break
                except hardware_controller.TimeoutError as e:
                    action = yield e

                    if action == ACTION_SKIP:
                        break

                    if action == ACTION_ABORT:
                        raise Aborted()

            if action == ACTION_SKIP:
                continue

        yield hw_mrc.scanbus(0)
        yield hw_mrc.scanbus(1)

def connect_and_apply_setup(setup, hw_registry, device_registry):
    gen = establish_connections(setup, hw_registry)
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            arg = yield obj
        except StopIteration:
            # From inside the generator
            break
        except GeneratorExit:
            # From the caller invoking close()
            gen.close()
            return

    gen = apply_setup(setup, hw_registry, device_registry)
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            arg = yield obj
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

def apply_setup(source, dest, device_registry):

    def _apply_device_config(src_dev, dest_mrc):
        action = ACTION_RETRY
        dest_dev = None

        while action == ACTION_RETRY:
            dest_dev = dest_mrc.get_device(src_dev.bus, src_dev.address)

            if dest_dev is not None:
                break

            action = yield MissingDestinationDevice(
                    url=src_dev.mrc.url, bus=src_dev.bus, dev=src_dev.address)

            if action == ACTION_SKIP:
                raise StopIteration()

            if action == ACTION_ABORT:
                raise Aborted()

        gen = apply_device_config(src_dev, dest_dev,
                device_registry.get_profile(src_dev.idc))
        arg = None

        while True:
            try:
                obj = gen.send(arg)
                arg = yield obj
            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return

    def _apply_mrc_config(src_mrc):
        action   = ACTION_RETRY
        dest_mrc = None

        while action == ACTION_RETRY:
            dest_mrc = dest.get_mrc(src_mrc.url)

            if dest_mrc is not None:
                break

            action = yield MissingDestinationMRC(url=src_mrc.url)

            if action == ACTION_SKIP:
                raise StopIteration()

            if action == ACTION_ABORT:
                raise Aborted()

        if not dest_mrc.is_connected():
            return

        for src_dev in src_mrc:
            action = ACTION_RETRY

            while action == ACTION_RETRY:

                gen = _apply_device_config(src_dev, dest_mrc)
                arg = None

                while True:
                    try:
                        obj = gen.send(arg)
                        arg = yield obj
                    except StopIteration:
                        action = None
                        break
                    except GeneratorExit:
                        gen.close()
                        return
                    except IDCConflict as e:
                        action = yield e

                        if action in (ACTION_SKIP, ACTION_RETRY):
                            break

                        if action == ACTION_ABORT:
                            raise Aborted()

    for src_mrc in source:
        gen = _apply_mrc_config(src_mrc)
        arg = None

        while True:
            try:
                obj = gen.send(arg)
                arg = yield obj
            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return
