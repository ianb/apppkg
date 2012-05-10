import sys
import os
import re
import yaml
import new
import subprocess
import urllib
from cStringIO import StringIO
from site import addsitedir
try:
    import simplejson as json
except ImportError:
    import json


__all__ = ['AppPackage', 'Environment']

here = os.path.dirname(os.path.abspath(__file__))


class AppPackage(object):

    def __init__(self, path, config_dir=None, environment=None):
        self.path = path
        fp = self.open('app.yaml')
        try:
            self.description = yaml.load(fp)
        finally:
            fp.close()
        if config_dir is None:
            config_dir = self.config_default_dir
        self.config_dir = config_dir
        self.environment = environment

    ## Helpers for file names and handling:

    def open(self, relpath, mode='rb'):
        return open(self.abspath(relpath), mode)

    def abspath(self, *paths):
        return os.path.normcase(os.path.abspath(os.path.join(self.path, *paths)))

    def exists(self, path):
        return os.path.exists(self.abspath(path))

    ## Properties to read and normalize specific configuration values:

    @property
    def name(self):
        return self.description['name']

    @property
    def static_path(self):
        """The path of static files"""
        if 'static' in self.description:
            return self.abspath(self.description['static'])
        elif self.exists('static'):
            return self.abspath('static')
        else:
            return None

    @property
    def wsgi_application(self):
        """The runner value (where the application is instantiated)"""
        runner = self.description.get('wsgi_application')
        if not runner:
            return None
        return CommandReference(self, runner, 'wsgi_application')

    @property
    def config_required(self):
        """Bool: is the configuration required"""
        return self.description.get('config', {}).get('required')

    @property
    def config_template(self):
        """Path: where a configuration template exists"""
        ## FIXME: should this be a command?
        v = self.description.get('config', {}).get('template')
        if v:
            return self.abspath(v)
        return None

    @property
    def config_validator(self):
        """Object: validator for the configuration"""
        v = self.description.get('config', {}).get('validator')
        if v:
            return CommandReference(self, v, 'config.validator')
        return None

    @property
    def config_default_dir(self):
        """Path: default configuration if no other is provided"""
        dir = self.description.get('config', {}).get('default')
        if dir:
            return self.abspath(dir)
        return None

    @property
    def requires(self):
        return Requires.from_description(self, self.description.get('requires'))

    ## Process initialization

    def activate_path(self, venv_path=None):
        dirs = self.description.get('add_paths', [])
        if isinstance(dirs, basestring):
            dirs = [dirs]
        dirs = [self.abspath(dir) for dir in dirs]
        add_paths = list(dirs)
        add_paths.extend([
            self.abspath('lib/python%s' % sys.version[:3]),
            self.abspath('lib/python%s/site-packages' % sys.version[:3]),
            self.abspath('lib/python'),
            self.abspath('vendor'),
            ])
        if venv_path:
            add_paths.extend([
                    os.path.join(venv_path, 'lib/python%s/site-packages' % sys.version[:3]),
                    ])
        for path in reversed(add_paths):
            self.add_path_to_sys_path(path)

    def setup_settings(self, settings=None):
        """Create the settings that the application itself can import"""
        if 'appsettings' not in sys.modules:
            module = new.module('appsettings')
            module.add_setting = _add_setting
            sys.modules[module.__name__] = module
        else:
            module = sys.modules['appsettings']
        if settings is not None:
            for name, value in settings.items():
                module.add_setting(name, value)

    def add_path_to_sys_path(self, path):
        """Adds one path to sys.path.

        This also reads .pth files, and makes sure all paths end up at the front, ahead
        of any system paths.  Also executes sitecustomize.py
        """
        if not os.path.exists(path):
            return
        old_path = [os.path.normcase(os.path.abspath(p)) for p in sys.path
                    if os.path.exists(p)]
        addsitedir(path)
        new_paths = list(sys.path)
        sys.path[:] = old_path
        new_sitecustomizes = []
        for path in new_paths:
            path = os.path.normcase(os.path.abspath(path))
            if path not in sys.path:
                sys.path.insert(0, path)
                if os.path.exists(os.path.join(path, 'sitecustomize.py')):
                    new_sitecustomizes.append(os.path.join(path, 'sitecustomize.py'))
        for sitecustomize in new_sitecustomizes:
            ns = {'__file__': sitecustomize, '__name__': 'sitecustomize'}
            execfile(sitecustomize, ns)

    def bytecompile(self):
        import compileall
        compileall.compile_dir(self.path)

    def call_script(self, script_path, arguments, env_overrides=None, cwd=None, python_exe=None,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE):
        """Calls a script, returning the subprocess.Proc object
        """
        env = os.environ.copy()
        script_path = os.path.join(self.path, script_path)
        if env_overrides:
            env.update(env_overrides)
        if not cwd:
            cwd = self.path
        if not python_exe:
            python_exe = sys.executable
        calling_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'call-script.py')
        args = [python_exe, calling_script, self.path, script_path]
        args.extend(arguments)
        env['APPPKG_LOCATION'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.Popen(args, stdout=stdout, stderr=stderr, stdin=stdin,
                                environ=env, cwd=cwd)
        return proc

    def initialize_for_script(self):
        """Initializes the environment for the purposes of a script"""
        venv = os.path.join(self.path, '.virtualenv')
        if not os.path.exists(venv):
            venv = None
        self.activate_path(venv)


class Requires(object):

    def __init__(self, app, pip=None, deb=None, rpm=None):
        ## FIXME: not sure if we need a reference to app
        self.app = app
        self.pip = pip
        self.deb = deb
        self.rpm = rpm

    @classmethod
    def from_config(cls, app, conf):
        if not conf:
            conf = {}
        return cls(deb=cls.normalize(conf.get('deb')),
                   rpm=cls.normalize(conf.get('rpm')),
                   pip=cls.normalize(conf.get('pip')),
                   app=app)

    @staticmethod
    def normalize(setting):
        if setting is None:
            return []
        if isinstance(setting, basestring):
            return [setting]
        return setting

    def install_deb(self, command='apt-get', sudo=False):
        if not self.deb:
            return
        cmd = [command, 'install'] + self.deb
        if sudo:
            cmd = ['sudo'] + cmd
        ## FIXME: we need a better way to run commands:
        self.run_command(cmd)

    def install_rpm(self, command='yum', gpgcheck=True, sudo=False):
        if not self.rpm:
            return
        cmd = [command, 'install', '-y']
        if not gpgcheck:
            cmd.append('--nogpgcheck')
        if sudo:
            cmd = ['sudo'] + cmd
        self.run_command(cmd)

    def run_command(self, cmd):
        subprocess.check_call(cmd)

    def create_venv(self, path):
        """Create a virtualenv at the path"""
        import virtualenv
        ## FIXME: configure virtualenv.logger?
        virtualenv.create_environment(
            path,
            site_packages=True,
            clear=False,
            unzip_setuptools=True,
            use_distribute=True,
            prompt=None,
            search_dirs=None,
            never_download=False)

    def install_pip(self, venv_path, make_venv=False):
        """Installs all the requirements in the requires: pip: ...

        Can create a virtualenv in the process; you should create a
        separate virtualenv for each application.
        """
        if not self.pip:
            return
        if make_venv:
            self.create_venv(venv_path)
        cmd = [os.path.join(venv_path, 'bin', 'pip'), 'install']
        for requirement in self.pip:
            if self.app.exists(requirement):
                # Assume it is a requirements file
                cmd.extend(['-r', self.app.abspath(requirement)])
            else:
                cmd.append(requirement)
        self.run_command(cmd)


class CommandReference(object):
    """Represents a reference to a command or object in the
    configuration.  Can be executed with ``.run()`` or an object
    extracted with ``.get_object()``
    """

    def __init__(self, app, ref, name):
        self.app = app
        self.ref = ref
        self.name = name
        self.ref_type, self.ref_data = self.parse_ref_type(ref)

    def __repr__(self):
        return '<CommandReference %s=%s for %r>' % (self.name, self.ref, self.app)

    _PY_MOD_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]+(?:\:[a-zA-Z_][a-zA-Z0-9_.]*)?$')

    def parse_ref_type(self, ref):
        if ref.startswith('/') or ref.startswith('url:'):
            if ref.startswith('url:'):
                ref = ref[4:]
            return 'url', (ref, None)
        if ref.startswith('script:'):
            ref = ref.split(':', 1)
            path = self.app.abspath(ref)
            with open(path) as fp:
                first = fp.readline()
            if first.startswith('#!') and 'python' in first:
                return 'py', (ref, None)
            return 'script', (ref, None)
        if ref.endswith('.py') or '.py:' in ref or ref.startswith('pyscript:'):
            if ref.startswith('pyscript:'):
                ref = ref[len('pyscript:'):]
            if ':' in ref:
                path, extra = ref.split(':', 1)
            else:
                path = ref
                extra = None
            return 'pyscript', (path, extra)
        if self._PY_MOD_RE.search(ref) or ref.startswith('py:'):
            if ref.startswith('py:'):
                ref = ref[3:]
            if ':' in ref:
                path, extra = ref.split(':', 1)
            else:
                path = ref
                extra = None
            return 'py', (path, extra)

    def run(self, *args, **kw):
        """Runs the command, returning (text_output, extra_data), or
        raising an exception"""
        return getattr(self, 'run_' + self.ref_type)(self.app.environment, *args, **kw)

    def run_url(self, *args, **kw):
        obj = self.app.wsgi_application.get_object()
        url = self.ref_data[0]
        if '?' in url:
            path, query_string = url.split('?', 1)
        else:
            path, query_string = url, ''
        all_args = []
        if args:
            for a in args:
                all_args.append(None, a)
        if kw:
            for name, value in sorted(kw.items()):
                all_args.append(name, value)
        if all_args:
            body = []
            for name, value in args:
                if isinstance(value, (int, float, str, unicode)):
                    value = urllib.quote(str(value))
                else:
                    value = urllib.quote(json.dumps(value))
                if name:
                    body.append('%s=%s' % (urllib.quote(name), value))
                else:
                    body.append(value)
            body = '&'.join(body)
        else:
            body = ''
        content_type = 'application/x-www-form-urlencoded'
        env = {
            'wsgi.url_scheme': 'http',
            'wsgi.input': StringIO(body),
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '0',
            'HTTP_HOST': 'http://localhost:0',
            'SCRIPT_NAME': '',
            'PATH_INFO': urllib.unquote(path),
            'QUERY_STRING': query_string,
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': len(body),
            }
        output = []
        status_headers = []

        def start_response(status, headers, exc_info=None):
            if exc_info:
                raise exc_info[0], exc_info[1], exc_info[2]
            status_headers[:] = [status, headers]
            return output.append
        app_iter = obj(env, start_response)
        output.extend(app_iter)
        status, headers = status_headers
        if status >= 300:
            ## FIXME: do some error thing?
            raise Exception()
        output = ''.join(output)
        metadata = {'headers': headers, 'status': status}
        return output, metadata

    def run_script(self, *args, **kw):
        if '.cmd' in kw:
            cmd = [kw.pop('.cmd')]
        else:
            cmd = [self.app.abspath(self.ref)]
        if '.exe' in kw:
            cmd.insert(0, kw.pop('.exe'))
        for name, value in sorted(kw.items()):
            if len(name) == 1:
                name = '-%s' % name
            else:
                name = '--%s' % name
            cmd.append(name)
            if value is True:
                pass
            elif isinstance(value, (int, float, str, unicode)):
                cmd.append(str(value))
            elif isinstance(value, basestring):
                cmd.append(value)
            else:
                cmd.append(json.dumps(value))
        cmd += list(args)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self.app.path)
        ## FIXME: should set env variables
        stdout, stderr = proc.communicate()
        metadata = {'stderr': stderr}
        return stdout, metadata

    def run_pyscript(self, *args, **kw):
        env = self.app.environment
        if env:
            executable = env.base_python_exe
        else:
            executable = sys.executable
        kw['.exe'] = executable
        kw['.cmd'] = self.ref[0]
        if self.ref[1] is not None:
            raise Exception(
                "The reference %s contains a function name, which doesn't work with run(): %s" % (self.name, self.ref[1]))
        return self.run_script(*args, **kw)

    def run_py(self, *args, **kw):
        obj = self.get_object()
        ## FIXME: catch stdout/stderr?
        try:
            result = obj(*args, **kw)
        except Exception, e:
            return None, {'exception': e}
        else:
            return result, {}

    def get_object(self):
        if self.ref_type == 'pyscript':
            filename = self.ref_data[0]
            name = self.ref_data[1]
            ns = {
                '__file__': filename,
                '__name__': os.path.splitext(os.path.basename(filename))[0],
                }
            execfile(filename, ns)
            ## FIXME: error check:
            return ns[name]
        else:
            modname = self.ref_data[0]
            name = self.ref_data[1]
            __import__(modname)
            mod = sys.modules[modname]
            return getattr(mod, name)


class Environment(object):

    def __init__(self, app, config=None, env_description=None, env_base=None,
                 base_python_exe=sys.executable, venv_location=None):
        self.app = app
        if config:
            if not os.path.isdir(config):
                raise Exception("The config directory (%r) must exist" % config)
        self.config = config
        check_jsonable(env_description)
        self.env_description = env_description
        if env_base:
            if not os.path.isdir(env_base):
                raise Exception("The env_base (%r) must be an existing dir" % env_base)
        self.env_base = env_base
        self.base_python_exe = base_python_exe
        self.venv_location = venv_location
        self.app.environment = self

    def run_command(self, command_path, args=None, env=None):
        if self.env_base:
            command_path = os.path.join(self.env_base, command_path)
        if env is None:
            env = {}
        env['_APPPKG_COMMAND_PATH'] = command_path
        env['_APPPKG_APP_PATH'] = self.app.path
        env['_APPPKG_PATH'] = here
        env['_APPPKG_ENV_DESCRIPTION'] = json.dumps(self.env_description)
        env['_APPPKG_CONFIG'] = self.config or ''
        env['_APPPKG_VENV_LOCATION'] = self.venv_location or ''
        full_env = os.environ.copy()
        full_env.update(env)
        command = [self.base_python_exe, os.path.join(here, 'run-command.py')]
        if args:
            command.extend(args)
        proc = subprocess.Popen(command, env=full_env, cwd=self.app.path,
                                stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return HandyProcess(proc, 'apppkg calling %s' % command_path)

    def run_func(self, command_path, func, *args, **kw):
        env = {
            '_APPPKG_ARGS': json.dumps(args),
            '_APPPKG_KW': json.dumps(kw),
            '_APPPKG_FUNC': func,
            }
        proc = self.run_command(command_path, env=env)
        data = json.loads(proc.stdout)
        if data.get('error'):
            raise FunctionException(data['error']['class'], data['error']['description'], data['error']['details'])
        return data['data']


class HandyProcess(object):

    def __init__(self, proc, description):
        self.proc = proc
        self._stdout = None
        self._stderr = None
        self.description = self.description

    def send_stdin(self, data=None):
        self._stdout, self._stderr = self.proc.communicate(data)
        if self.proc.returncode:
            raise ProcessError(self.proc.returncode, self, self.description)

    @property
    def stdout(self):
        if self._stdout is None:
            self.send_stdin()
        return self._stdout

    @property
    def stderr(self):
        if self._stderr is None:
            self.send_stdin()
        return self._stderr


class ProcessError(Exception):

    def __init__(self, code, process, description):
        self.code = code
        self.process = process
        self.description = description

    def __str__(self):
        return '<ProcessError returncode=%r running %s>' % (self.code, self.description)


class FunctionException(Exception):

    def __init__(self, class_name, description, details):
        self.class_name = class_name
        self.description = description
        for name, value in details.items():
            setattr(self, name, value)

    def __str__(self):
        return '<FunctionException:%s %s>' % (self.class_name, self.description)


def _add_setting(name, value):
    import appsettings
    check_jsonable(name, value)
    setattr(appsettings, name, value)


def check_jsonable(name, value):
    if isinstance(value, dict):
        for n, v in value.items():
            if not isinstance(name, basestring):
                raise ValueError("%s is a dict with a non-string key (%r)" % (name, n))
            n = name + '.' + n
            check_jsonable(n, v)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            n = '%s[%r]' % (name, i)
            check_jsonable(n, v)
    elif isinstance(value, (str, unicode, int, float, bool)) or value is None:
        pass
    else:
        raise ValueError("%s (%r) is not a JSONable type (%s)"
                         % (name, value, type(value)))
