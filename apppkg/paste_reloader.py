# Copied from paste.reloader:
"""
Use this like::

    import reloader
    reloader.install()

Then make sure your server is installed with a shell script like::

    err=3
    while test "$err" -eq 3 ; do
        python server.py
        err="$?"
    done

or restart in Python (server.py does this).  Use the watch_file(filename)
function to cause a reload/restart for other other non-Python files (e.g.,
configuration files).
"""

import os
import sys
import time
import threading
import atexit

# Copied from paste.util.classinstance:
class classinstancemethod(object):
    """
    Acts like a class method when called from a class, like an
    instance method when called by an instance.  The method should
    take two arguments, 'self' and 'cls'; one of these will be None
    depending on how the method was called.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, type=None):
        return _methodwrapper(self.func, obj=obj, type=type)

class _methodwrapper(object):

    def __init__(self, func, obj, type):
        self.func = func
        self.obj = obj
        self.type = type

    def __call__(self, *args, **kw):
        assert not kw.has_key('self') and not kw.has_key('cls'), (
            "You cannot use 'self' or 'cls' arguments to a "
            "classinstancemethod")
        return self.func(*((self.obj, self.type) + args), **kw)

    def __repr__(self):
        if self.obj is None:
            return ('<bound class method %s.%s>'
                    % (self.type.__name__, self.func.func_name))
        else:
            return ('<bound method %s.%s of %r>'
                    % (self.type.__name__, self.func.func_name, self.obj))

def install(poll_interval=1, raise_keyboard_interrupt=True):
    mon = Monitor(poll_interval=poll_interval,
                  raise_keyboard_interrupt=raise_keyboard_interrupt)
    t = threading.Thread(target=mon.periodic_reload)
    t.start()
    
class Monitor:

    instances = []
    global_extra_files = []

    def __init__(self, poll_interval, raise_keyboard_interrupt):
        self.module_mtimes = {}
        atexit.register(self.atexit)
        self.keep_running = True
        self.poll_interval = poll_interval
        self.raise_keyboard_interrupt = raise_keyboard_interrupt
        self.extra_files = self.global_extra_files[:]
        self.instances.append(self)

    def atexit(self):
        self.keep_running = False
        if self.raise_keyboard_interrupt:
            # This exception is somehow magic, because it applies
            # to more threads and situations (like socket.accept)
            # that a mere SystemExit will not.
            raise KeyboardInterrupt("Exiting process")

    def periodic_reload(self):
        while 1:
            if not self.keep_running:
                break
            if not self.check_reload():
                os._exit(3)
                break
            time.sleep(self.poll_interval)

    def check_reload(self):
        filenames = self.extra_files[:]
        for module in sys.modules.values():
            try:
                filenames.append(module.__file__)
            except AttributeError:
                continue
        for filename in filenames:
            try:
                mtime = os.stat(filename).st_mtime
            except (OSError, IOError):
                continue
            if filename.endswith('.pyc') and os.path.exists(filename[:-1]):
                mtime = max(os.stat(filename[:-1]).st_mtime, mtime)
            if not self.module_mtimes.has_key(filename):
                self.module_mtimes[filename] = mtime
            elif self.module_mtimes[filename] < mtime:
                print >> sys.stderr, (
                    "%s changed; reloading..." % filename)
                return False
        return True

    def watch_file(self, cls, filename):
        filename = os.path.abspath(filename)
        if self is None:
            for instance in cls.instances:
                instance.watch_file(filename)
            cls.global_extra_files.append(filename)
        else:
            self.extra_files.append(filename)

    watch_file = classinstancemethod(watch_file)

watch_file = Monitor.watch_file
