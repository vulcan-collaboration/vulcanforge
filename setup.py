# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

from vulcanforge import __version__

PROJECT_DESCRIPTION = '''
VulcanForge is an open source "Forge Framework", where a forge is a web site
that manages artifact repositories, bug reports, discussions, mailing
lists, wiki pages, blogs and more for any number of individual projects.

It is derived from the Allura project by Sourceforge.
'''

setup(
    name='VulcanForge',
    version=__version__,
    description='Base distribution of the VulcanForge development platform',
    long_description=PROJECT_DESCRIPTION,
    author='Vanderbilt ISIS',
    author_email='',
    url='',
    keywords='vulcanforge turbogears pylons jinja2 mongodb',
    license='Apache License, http://www.apache.org/licenses/LICENSE-2.0',
    platforms=['Linux', 'MacOS X'],
    classifiers=[
        'Framework :: Pylons',
        'Framework :: TurboGears',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Framework',
        'License :: OSI Approved :: Apache Software License',
    ],
    install_requires=[
        'tg.devtools == 2.2.2',
        'simplejson >= 3.3.2',
        'FormEncode == 1.2.4',
        'ipython  < 6.0.0',
        "docutils < 0.10",
        "Genshi < 0.7",
        "WebTest < 2",
        "WebOb == 1.1.1",
        "TurboGears2==2.2.2",
        "Pylons >= 1.0",
        "Ming",
        "boto < 2.25.0",
        "PasteScript",
        "Babel >= 0.9.4",
        "pymongo >= 3.0",
        "pysolr",
        "Markdown >= 2.6.7",
        "bleach >= 1.5",
        "Pygments >= 1.1.1",
        "PyYAML >= 3.09",
        "python-openid >= 2.2.4",
        "python-dateutil >= 1.4.1",
        "EasyWidgets==0.2dev-20130716",
        "Pillow >= 1.1.7",
        "iso8601",
        "chardet == 1.0.1",
        "feedparser >= 5.0.1",
        "oauth2 == 1.2.0",
        "jsmin == 2.0.3",
        "cssmin",
        "pycrypto",
        "pyScss == 1.2.0.post3",
        "requests",
        "jinja2",
        "BeautifulSoup==3.2.1",
        "python-markdown-oembed < 0.2.0",
        "redis == 2.7.2",
        "hiredis",
        "gevent>=1.0",
        "gevent-websocket>=0.9",
        "jsonschema",
        "pdfminer",
        'pyotp >= 2.1.1',
        'qrcode >= 5.2.2',
        "pyclamd",
        "pydenticon >= 0.3"
    ],
    setup_requires=["PasteScript >= 1.7"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    tests_require=[
        'pytidylib',
        'poster',
        'nose'
    ],
    package_data={
        'vulcanforge': [
            'i18n/*/LC_MESSAGES/*.mo', 'templates/*/*', 'public/*/*']
    },
    message_extractors={
        'vulcanforge': [
            ('**.py', 'python', None),
            ('templates/**.mako', 'mako', None),
            ('templates/**.html', 'genshi', None),
            ('public/**', 'ignore', None)]
    },
    entry_points="""
    [paste.paster_command]
    create-vulcanapp = vulcanforge.command.create_vulcanapp:CreateVulcanAppCommand

    eventd = vulcanforge.command.eventd:EventdCommand
    taskd = vulcanforge.command.taskd:TaskdCommand
    task = vulcanforge.command.taskd:TaskCommand
    run_migrations = vulcanforge.command.migration:MigrationCommand
    models = vulcanforge.command:ShowModelsCommand
    reindex = vulcanforge.command:ReindexCommand
    reindex_globals = vulcanforge.command:ReindexGlobalsCommand
    reindex_notifications = vulcanforge.command:ReindexNotifications
    reindex_exchange = vulcanforge.command:ReindexExchangeCommand
    register-project-template = vulcanforge.command:RegisterProjectTemplate
    ensure_index = vulcanforge.command:EnsureIndexCommand
    ensure-project-creation = vulcanforge.command:EnsureProjectCreationCommand
    script = vulcanforge.command:ScriptCommand
    set-tool-access = vulcanforge.command:SetToolAccessCommand
    smtp_server = vulcanforge.command:SMTPServerCommand
    create-neighborhood = vulcanforge.command:CreateNeighborhoodCommand
    sync_visualizers = vulcanforge.visualize.command:SyncVisualizersCommand
    re_run_visualizers = vulcanforge.visualize.command:ReRunVisualizersCommand
    forgeadmin-tools = vulcanforge.command:ForgeAdminToolsCommand
    list_users = vulcanforge.command.user:ListUsersCommand
    createuser = vulcanforge.command.user:CreateUserCommand
    stage-static-resources = vulcanforge.resources.command:StageStaticResources
    expire-passwords = vulcanforge.command.user:ExpirePasswordsCommand
    reset-password-history = vulcanforge.command.user:ResetPasswordHistoryCommand
    expire-users = vulcanforge.command.user:ExpireUsersCommand
    enable-user = vulcanforge.command.user:EnableUserCommand
    disable-user = vulcanforge.command.user:DisableUserCommand
    refresh-users = vulcanforge.command.user:RefreshUsersCommand
    verify-accounts = vulcanforge.command.user:VerifyAccountsCommand
    vshell = vulcanforge.command.util:VulcanForgeShellCommand
    install_tool = vulcanforge.command.project:InstallTool
    add-user-to-project = vulcanforge.command.project:AddUserToProject
    wiki-export = vulcanforge.command.wiki_tool:ExportWikiPages
    wiki-import = vulcanforge.command.wiki_tool:ImportWikiPages
    wiki_findbroken = vulcanforge.command.wiki_tool:FindBrokenLinks
    purge-project = vulcanforge.command.project:PurgeProject
    cleanup_for_application_start = vulcanforge.command.cleanup:CleanupForApplicationStart
    turn_fail_whale_on = vulcanforge.command.fail_whale:TurnFailWhaleOnCommand
    turn_fail_whale_off = vulcanforge.command.fail_whale:TurnFailWhaleOffCommand
    scan-files = vulcanforge.command.virus_scan:ScanFiles

    [easy_widgets.engines]
    jinja = vulcanforge.config.render.jinja:JinjaEngine
    """,
    dependency_links=[
        "http://tg.gy/current/",
        "git+https://git.code.sf.net/p/merciless/code@pymongo-30#egg=Ming"
    ],
    zip_safe=False
)
