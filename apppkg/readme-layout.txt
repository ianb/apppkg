Welcome to your fancy new apppkg setup.  This file describes a bit of
how you can use this layout.

This layout is setup to host your code, but also to help you manage
libraries and dependencies for your application.

It is intended that you put your "main" application code in
%(pkg_name)s-src/ - so that %(pkg_name)s-src/%(pkg_name)s/ is the
package.  (The -src is included to distinguish between the directory
containing the package and the package itself.)  You can rearrange
this if you want.  For example:

  $ mkdir src
  $ mv %(pkg_name)s-src src/%(pkg_name)s
  # Then edit app.yaml to point to the new location

You'll notice a file %(pkg_name)s-src/sitecustomize.py where you can
put code that will always be run at startup (before scripts or
libraries or anything else).

The file app.yaml contains information about your application.  We've
put several examples in there, with stub code in
%(pkg_name)s-src/%(pkg_name)s/entrypoints.py

For managing your libraries, there is a file .pip.conf which controls
pip when you run it from within this directory (or a subdirectory).

When used like this, libraries will be installed into vendor/.  You
can (and should!) check this directory into version control.  Also
bin/ will contain scripts.  If a library contains binary components
and is not portable it will instead be installed into vendor-binary/
(this directory will be created on demand).  You should not check this
directory into version control!  Instead the libraries in there should
be reinstalled on new systems.  You can note these libraries in
requirements.txt

You may be familiar with requirements.txt from other deployment
systems.  For apppkg you should consider it a last resort - vendor/ is
a safer and simpler system for most libraries.  Also note that you can
ask that instead of installing libraries with pip -r requirements,
that they be installed with your native packaging system.  Do
something like this in app.yaml:

requires:
  deb:
    - python-lxml
  rpm:
    - python-lxml
  requires:
    - lxml

Systems should use the deb or rpm method if they can, and then only
use the requires value as confirmation.  I especially recommend this
for database drivers.

How the directory is assembled is up to you.  You may want to use a
script to check things out, or use git submodules, svn externals,
whatever works for you.
