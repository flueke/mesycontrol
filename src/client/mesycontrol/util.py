from PyQt4.QtCore import QObject, QTimer
import gc
import os
import sys
from mesycontrol import application_model

class GarbageCollector(QObject):
    '''
    Disable automatic garbage collection and instead collect manually
    every INTERVAL milliseconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash.
    '''

    INTERVAL = 1000

    def __init__(self, parent=None, debug=False):
        QObject.__init__(self, parent)
        self.debug = debug

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        gc.disable()
        self.timer.start(self.INTERVAL)

    def check(self):
        #return self.debug_cycles() # uncomment to just debug cycles
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print ('gc_check called:', l0, l1, l2)
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print ('collecting gen 0, found:', num, 'unreachable')
            if l1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    print ('collecting gen 1, found:', num, 'unreachable')
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print ('collecting gen 2, found:', num, 'unreachable')

    def debug_cycles(self):
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))

def find_data_dir(main_script_file):
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        while os.path.islink(exe):
            lnk = os.readlink(exe)
            if os.path.isabs(lnk):
                exe = lnk
            else:
                exe = os.path.abspath(os.path.join(os.path.dirname(exe), lnk))
        return os.path.dirname(exe)
    return os.path.dirname(main_script_file)

def find_data_file(filename):
    return os.path.join(application_model.instance.data_dir, filename)
