# -*- coding: utf-8 -*-

"""
configdiff

@author: U{tannern<tannern@gmail.com>}
"""


import sys
import ConfigParser
from optparse import OptionParser


USAGE = "usage: configdiff.py [options] source destination"
OPT_PARSER = OptionParser(usage=USAGE)
OPT_PARSER.add_option('-w', "--write",
                      action="store_true", dest="save_changes", default=False,
                      help="Offer to update each differing option in "
                           "destination with the corresponding value from"
                           "source")
OPT_PARSER.add_option('-o', '--outfile',
                      dest="outfile", default=None,
                      help="Write output to this file if --write is true. "
                           "Defaults to overwrite destination file.")
OPT_PARSER.add_option('-s', '--skip',
                      action="append", dest="skiplist",
                      help="Skip options by name. May be specified multiple"
                           "times.")


def _parse_file(path):
    parser = ConfigParser.ConfigParser()
    with open(path, 'r') as fp:
        parser.readfp(fp)
    return parser


def _raw_input_as_bool(prompt=None):
    input_val = raw_input(prompt or "")
    try:
        return input_val.lower()[0] in 'ty'
    except IndexError:
        return False

if __name__ == "__main__":
    parsed_args = OPT_PARSER.parse_args()
    try:
        (options, (src_path, dst_path)) = parsed_args
        msg = ("Comparing config files:{}\n"
               "  source.....: {}\n"
               "  destination: {}\n").format(
            " READ ONLY" if not options.save_changes else "",
            src_path, dst_path)
        sys.stdout.write(msg)
    except ValueError:
        sys.stderr.write("Wrong number of arguments\n" + USAGE + "\n")
        sys.exit(1)

    src_config = _parse_file(src_path)
    dst_config = _parse_file(dst_path)

    sys.stdout.write('Checking section: [{}]...\n'.format('DEFAULT'))
    for opt_name, src_val in src_config.defaults().items():
        if opt_name in options.skiplist:
            continue
        try:
            dst_val = dst_config.get('DEFAULT', opt_name)
        except ConfigParser.NoOptionError:
            dst_val = ""
        if dst_val != src_val:
            sys.stdout.write('  option: {}\n'
                             '    source.....: {}\n'
                             '    destination: {}\n'.format(opt_name,
                                                            src_val,
                                                            dst_val))
            sys.stdout.flush()
            if options.save_changes:
                prompt = "    copy source value to destination? y/[n] "
                if _raw_input_as_bool(prompt):
                    dst_config.set('DEFAULT', opt_name, src_val)

    for section in src_config.sections():
        sys.stdout.write('Checking section: [{}]...'.format(section))
        if not dst_config.has_section(section):
            sys.stdout.write(' not found in destination\n'.format(section))
            sys.stdout.flush()
            continue
        else:
            sys.stdout.write('\n')
            sys.stdout.flush()
        for opt_name, src_val in src_config.items(section):
            if opt_name in options.skiplist:
                continue
            try:
                dst_val = dst_config.get(section, opt_name)
            except ConfigParser.NoOptionError:
                dst_val = ""
            if dst_val != src_val:
                sys.stdout.write('  option: {}\n'
                                 '    source.....: {}\n'
                                 '    destination: {}\n'.format(opt_name,
                                                                src_val,
                                                                dst_val))
                sys.stdout.flush()
                if options.save_changes:
                    prompt = "    copy source value to destination? y/[n] "
                    if _raw_input_as_bool(prompt):
                        dst_config.set(section, opt_name, src_val)

    if options.save_changes:
        if options.outfile is None:
            options.outfile = dst_path
        sys.stdout.write('Writing updated destination file at '
                         '{}...'.format(options.outfile))
        sys.stdout.flush()
        with open(options.outfile, 'w') as fp:
            dst_config.write(fp)
        sys.stdout.write('done\n'.format(options.outfile))
        sys.stdout.flush()

    sys.exit(0)
