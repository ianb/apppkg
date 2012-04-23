"""Creates a simple app layout"""

import argparse
import os

parser = argparse.ArgumentParser(
    prog='python -c apppkg.init',
    description="Create a new apppkg layout",
    )

parser.add_argument(
    'dir', metavar="DIR",
    help="Directory to write to.")

parser.add_argument(
    '--name', metavar='NAME',
    help="Name of the application (defaults to directory name)")


TEMPLATE_DIRS = [
    '.',
    '%(pkg_name)s/%(pkg_name)s',
    'vendor',
    ]

TEMPLATE_FILES = {

    'app.yaml': """\
platform: python wsgi
name: %(name)s
add_paths:
  - %(pkg_name)s
requires:
  pip: requirements.txt
wsgi: %(pkg_name)s.entrypoints:make_app()
wsgi_ping: /.ping
install: %(pkg_name)s.entrypoints:install
before_update: %(pkg_name)s.entrypoints:before_update
update: %(pkg_name)s.entrypoints:update
health_check: %(pkg_name)s.entrypoints:health_check
before_delete: %(pkg_name)s.entrypoints:before_delete
check_environment: %(pkg_name)s.entrypoints:check_environment
""",

    '%(pkg_name)s/%(pkg_name)s/entrypoints.py': """\
# Each of the functions here is referred to in app.yaml
# They start out simply stubbed out

def make_app():
    # should return a WSGI application
    from %(pkg_name)s.something import Application
    return Application()

def install():
    # You might create db tables or setup files or something here
    pass

def before_update():
    # This version of the application is about to be overwritten by
    # a new version.  Do something here, not sure what?
    pass

def update():
    # This application has just been updated.  You might want to migrate
    # database tables to a new schema here, for example
    # The safest thing to do is to treat everything like an install or update:
    install()

def before_delete():
    # The application is about to be deleted (not just updated).  Do something?
    pass

def health_check():
    # You should do checks on data integrity here
    pass

def check_environment():
    # If you need a command or utility you should check it here
    # E.g., check that $PATH/git exists if you need to use git
    pass
""",

    '%(pkg_name)s/%(pkg_name)s/__init__.py': """\
""",
    '%(pkg_name)s/sitecustomize.py': """\
# You can put code here that will be run when the process is setup
""",

    '.pip.conf': """\
[global]
sys.path =
    %%(here)s/vendor
    %%(here)s/vendor-binary

[install]
install_option =
    --install-purelib=%%(here)s/vendor/
    --install-platlib=%%(here)s/vendor-binary/
    --install-scripts=%%(here)s/bin/
""",

    '.gitignore': """\
vendor-binary
""",

    'requirements.txt': """\
# You MAY put libraries here that you require.
# You SHOUlD instead try to use "pip install" to install things into vendor/
# You WILL notice some libraries end up in vendor-binary/ : these are libraries
# that must be built locally.  You should put those libraries into this file.
# You are NOT recommended to use "pip freeze" to generate this file, as it will
# include libraries should be present in vendor/
"""
    }


def sub(c, vars):
    return c % vars


def make_package_name(name):
    return name.lower().replace(' ', '_')


def main():
    args = parser.parse_args()
    if not args.name:
        args.name = os.path.basename(args.dir).strip('/').strip('\\')
    vars = dict(
        name=args.name,
        dir=args.dir,
        pkg_name=make_package_name(args.name),
        )
    for dir in TEMPLATE_DIRS:
        dir = os.path.join(args.dir, sub(dir, vars))
        if not os.path.exists(dir):
            print 'Creating %s/' % dir
            os.makedirs(dir)
    for name, content in TEMPLATE_FILES.items():
        name = os.path.join(args.dir, sub(name, vars))
        content = sub(content, vars)
        if os.path.exists(name):
            with open(name, 'rb') as fp:
                existing = fp.read()
            if existing == content:
                print 'No changes to %s' % name
                continue
            print 'Overwriting %s' % name
        else:
            print 'Writing %s' % name
        with open(name, 'wb') as fp:
            fp.write(content)


if __name__ == '__main__':
    main()
