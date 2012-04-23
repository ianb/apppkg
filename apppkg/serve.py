"""Serve an app locally/for development"""
import os
import sys
import subprocess
import shlex
import argparse
from apppkg import paste_httpserver as httpserver
from apppkg import AppPackage


here = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(
    description="Serve the application locally")

parser.add_argument(
    '--app', metavar="DIR",
    default='.',
    help="Location where the app is located (defaults to current directory)")

parser.add_argument(
    '-H', '--host', metavar='INTERFACE/IP',
    default='127.0.0.1',
    help="The interface to connect to; 127.0.0.1 (default) only allows local connections.  "
    "0.0.0.0 opens connections on all interfaces (making your server public).")

parser.add_argument(
    '-p', '--port', metavar='PORT',
    default='8080',
    help="The port to connect to (default %(default)s).  Connecting to a port below 1024 "
    "typically requires root permissions")


def main():
    options = parser.parse_args()
    command_serve(options)


def command_serve(options):
    dir = os.path.abspath(options.dir)
    if not os.path.exists(os.path.join(dir, 'app.yaml')):
        print "Could not find app.yaml in %s" % dir
        sys.exit(1)
    app = AppPackage(dir)
    ## FIXME: here is where I should configure the app
    if 'wsgi' in app.platform:
        serve_python(options, app)
    else:
        print 'I do not know how to serve this kind of application'


def serve_python(options, app):
    dir = os.path.abspath(dir)
    app.run_command(
        os.path.join(here, 'server-httpserver.py'),
        env={
            '_APPPKG_SERVE_HOST': options.host,
            '_APPPKG_SERVE_PORT': options.port,
            }

        cmd = [sys.executable,
               os.path.abspath(os.path.join(__file__, '../../devel-runner.py')),
               dir]
    ## FIXME: should cut down the environ significantly
    environ = os.environ.copy()
    environ['SILVER_INSTANCE_NAME'] = 'localhost'
    environ['SILVER_PASTE_LOCATION'] = httpserver.__file__
    environ['SILVER_SERVE_HOST'] = options.host
    environ['SILVER_SERVE_PORT'] = options.port
    proc = None
    try:
        try:
            while 1:
                try:
                    proc = subprocess.Popen(cmd, cwd=dir, env=environ)
                except:
                    print 'Error running command: %s' % ' '.join(cmd)
                    raise
                proc.communicate()
                if proc.returncode == 3:
                    # Signal to do a restart
                    print 'Restarting...'
                else:
                    return
            sys.exit(proc.returncode)
        finally:
            if (proc is not None
                and hasattr(os, 'kill')):
                import signal
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except (OSError, IOError):
                    pass
    except KeyboardInterrupt:
        print 'Terminating'


def call_script(app_config, script):
    run([sys.executable, os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                      'mgr-scripts', 'call-script.py'),
         app_config.app_dir] + shlex.split(script))


def _turn_sigterm_into_systemexit():
    """
    Attempts to turn a SIGTERM exception into a SystemExit exception.
    """
    try:
        import signal
    except ImportError:
        return

    def handle_term(signo, frame):
        raise SystemExit
    signal.signal(signal.SIGTERM, handle_term)


def search_path(exe_names):
    ## FIXME: should I allow for some general environmental variable override here?
    paths = os.environ['PATH'].split(os.path.pathsep)
    for name in exe_names:
        for path in paths:
            if os.path.exists(os.path.join(path, name)):
                return name
    return exe_names[0]
