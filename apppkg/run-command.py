#!/usr/bin/env python
import os
import sys
try:
    import simplejson as json
except ImportError:
    import json
import new
apppkg = None


command_path = os.environ['_APPPKG_COMMAND_PATH']
app_path = os.environ['_APPPKG_APP_PATH']
apppkg_path = os.environ['_APPPKG_PATH']
env_description = json.loads(os.environ['_APPPKG_ENV_DESCRIPTION'])
config_dir = os.environ['_APPPKG_CONFIG'] or None
venv_location = os.environ['_APPPKG_VENV_LOCATION'] or None
args = sys.argv[1:]


def setup_apppkg():
    """Sets up apppkg so it is importable.

    Does it the hard way so we don't have to add the parent directory
    to the path (since the parent directory might contain a bunch of
    other modules)
    """
    global apppkg
    if 'apppkg' in sys.modules:
        if apppkg is None:
            import apppkg
        return
    mod = sys.modules['apppkg'] = new.module('apppkg')
    mod.__path__ = apppkg_path
    mod.__file__ = os.path.join(apppkg_path, '__init__.py')
    execfile(mod.__file__, mod.__dict__)
    import apppkg


def make_app():
    app = apppkg.AppPackage(app_path, config_dir)
    return app


def setup_settings(app):
    app.setup_settings()
    if not env_description:
        return
    import appsettings
    for name, value in env_description.items():
        setattr(appsettings, name, value)
    appsettings.config_dir = config_dir


def strip_json_attrs(d):
    for key in list(d):
        try:
            json.dumps(dict[key])
        except TypeError:
            del d[key]


def main():
    setup_apppkg()
    app = make_app()
    env_description['config_dir'] = config_dir
    app.setup_settings(env_description)
    app.activate_path(venv_location)
    import appsettings
    appsettings.app = app
    d = {
        '__name__': '__main__',
        '__file__': command_path,
        }
    execfile(command_path, d)
    if os.environ('_APPPKG_FUNC'):
        try:
            func = d[os.environ['_APPPKG_FUNC']]
            args = json.loads(os.environ['_APPPKG_ARGS'])
            kw = json.loads(os.environ['_APPPKG_KW'])
            resp = func(*args, **kw)
            resp = {'data': resp}
            resp = json.dumps(resp)
        except Exception, e:
            resp = {
                'error': {
                    'class': e.__class__.__name__, 'description': str(e), 'details': strip_json_attrs(e.__dict__),
                    }
                }
            resp = json.dumps(resp)
        sys.stdout.write(resp)


if __name__ == '__main__':
    main()
