# Vulcan

Vulcan is a framework for enterprise collaboration platforms originally created
for the DARPA Adaptive Vehicle Make (AVM) Program.  There, it provded a foundation
for VehicleFORGE, a platform for cyber-physical system design used to host
AVM's Fast Adaptive Next-Generation (FANG) vehicle design challenges.

VehicleFORGE originated as an early fork of SourceForge's Allura platform, which
is today Apache Allura.  Vulcan was motivated by providing a better organization
as a framework and by adding new forms of extensibility for adapting platform features
and services to an enterprise. 

Vulcan is comprised of a core part and a set of optional annexes.
**This repository provides the core part, VulcanForge.**

## Micro-Service Dependencies

Vulcan employs MongoDB for document persistence, Apache Solr for indexing, and Redis
as a key-object store.  In the current release, the following versions of these
dependencies are known to be compatible:

  - MongoDB 3.4.4
  - Apache Solr 6.5.0
  - Redis 3.2.8

Vulcan applications assume these micro-services are deployed in a manner reflecting
the application's requirements.  Deployments of Apache Solr are supported by assets
provided in the *solr\_config* directory.

## Cloud Object Storage

Vulcan employs cloud object storage for artifact persistence, requiring an object
service supporting an AWS S3-compatible API that is accessed via the Python *boto*
package.  This requirement has been satisfied in private cloud deployments using
OpenStack Swift, for example.

## Installation and Creating Applications

Installed alone, VulcanForge supports creating new framework applications from
templates.  When doing so, we recommend using a virtual environment.
Below is a basic procedure.

 1. Clone this repository.
 2. Create and initialize a virtualenv.

        $ virtualenv vf_venv
        $ . vf_venv/bin/activate

 3. Change directory into this repository's root directory.
 4. Install VulcanForge.

        $ pip install -r requirements.txt
        $ python setup.py develop

 5. Create an application

        $ paster create-vulcanapp -h

        Usage: paster create-vulcanapp [options] <package> <target directory (defaults to current)>
        Creates a new vulcan application
        
        Options:
          -h, --help            show this help message and exit
          -v, --verbose
          -n NAME, --name=NAME  Project name (defaults to name of package)
          -r, --repos           Application includes support for repositories (should
                                have vulcanrepo installed)
          -t TEMPLATE, --template=TEMPLATE
                                Path to custom application template (file path or url

## Vulcan Applications

Vulcan applications created using *create-vulcanapp* will have a canonical
organization that can be used to selectively extend and refine potions of
the framework.  Also included in the created application are two prototype
configuration files: *development.ini* and *production.ini*.  The first
provides a commented guide to configuring the application.  The second provides
a set of configuration items specifically for production deployments as 
differences from those in *development.ini*. 

Applications can be served using WSGI-compatible web servers;
for example, Apache with mod_wsgi.  For development, applications can be 
served using *paster serve*.

# Release Notes

## Version 2.0.2

Minor Python packaging changes.

## Version 2.0.1

This is a minor feature release.

 - Disable gravatar support by configuration setting

## Version 2.0.0

This release is compatible with the Ubuntu Xenial LTS. It is highly recommended 
for all application deployments, as it includes critical security fixes to 
previous releases.

 - Support added for installing VulcanForge using pip via a requirements file.
 - Markdown sanitization is now performed using the Python *bleach* module,
which resolves vulnerabilities detected by penetration testing.
 - A new core tool type *catalog* is added a foundation for tools that manage 
versioned bundles of metadata and artifacts.
 - Vulcan projects now better support sub-typing and polymorphic querying.  
*Project.query.get* and *Project.query.find* continue to operate on the base type 
for compatibility.  New *query\_get* and *query\_find* methods are subtype-aware.
 - Solr configuration assets are now included directly in VulcanForge and are
compatible with Solr 6.5.0.  When upgrading Vulcan applications to Solr 6.5.0 
from previous releases, Solr indexes must be rebuilt using the *reindex\_globals* 
and *reindex* commands.
 - For compatibility with MongoDB and PyMongo 3+, VulcanForge now installs the 
Ming ODM from a branch of its development repository *pymongo-30* rather than 
the Ming project's PyPI packages.
