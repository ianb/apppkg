"""This is meant to be called specifically with pip install --script-fixup=apppkg.scriptfixup:fixup"""

def fixup(scripts):
    for req, script in scripts:
        _fixup_script(script)

TEMPLATE = """\
#!/usr/bin/env python
## This is all apppkg boilerplate for activating the environment:
import os
base = os.path.dirname(os.path.abspath(__file__))
# Now we walk up until we can find app.yaml
old_base = None
while not os.path.exists(os.path.join(base, 'app.yaml')):
    old_base = base
    base = os.path.dirname(base)
    if base == old_base:
        raise Exception('Cannot locate app.yaml above script %s' % __file__)
import apppkg
app = apppkg.AppPackage(base)
app.initialize_for_script()

## Here is the normal script:

__CONTENT__
"""

def _fixup_script(script):
    fp = open(script)
    # Skip the #! line:
    fp.readline()
    content = fp.read()
    fp.close()
    script_content = TEMPLATE.replace('__CONTENT__', content)
    fp = open(script, 'w')
    fp.write(script_content)
    fp.close()
