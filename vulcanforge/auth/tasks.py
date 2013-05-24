import logging
import subprocess
import re

try:
    import ldap
    from ldap import modlist
except ImportError:
    ldap = modlist = None

from tg import config

from vulcanforge.taskd import task


LOG = logging.getLogger(__name__)


class SchrootError(Exception):
    pass


@task
def reset_ldap_users():
    p = subprocess.Popen(
        ['schroot', '-d', '/', '-c', config['auth.ldap.schroot_name'], '-u',
         'root', '/ldap-userconfig.py', 'clear_all'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    rc = p.wait()
    if rc != 0:
        errmsg = p.stdout.read()
        LOG.error('Error clearing user home directories: %s', errmsg)
        raise SchrootError(errmsg)


@task
def register_ldap(username):
    p = subprocess.Popen(
        ['schroot', '-d', '/', '-c', config['auth.ldap.schroot_name'], '-u',
         'root', '/ldap-userconfig.py', 'init', username],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    rc = p.wait()
    if rc != 0:
        errmsg = p.stdout.read()
        LOG.error('Error creating home directory for %s: %s', username, errmsg)
        raise SchrootError(errmsg)


@task
def upload_ssh_ldap(username, pubkey):
    p = subprocess.Popen(
        ['schroot', '-d', '/', '-c', config['auth.ldap.schroot_name'], '-u',
         'root', '/ldap-userconfig.py', 'upload', username, pubkey],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    rc = p.wait()
    if rc != 0:
        errmsg = p.stdout.read()
        LOG.error('Error uploading public SSH key for %s: %s',
                  username, errmsg)
        raise SchrootError(errmsg)


@task
def remove_workspacetabs(href, regex=True, **kw):
    from vulcanforge.auth.model import WorkspaceTab
    if regex:
        href = re.compile(href)
    query = {"href": href}
    query.update(kw)
    for tab in WorkspaceTab.query.find(query):
        tab.delete()
