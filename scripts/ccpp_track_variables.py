#!/usr/bin/env python

# Standard modules
import argparse
import logging
import collections
#import importlib
#import itertools
import os
import glob
import re
#import sys

# CCPP framework imports
#from common import encode_container, decode_container, decode_container_as_dict, execute
from metadata_parser import parse_scheme_tables, read_new_metadata
from metadata_table import find_scheme_names, parse_metadata_file
from ccpp_prebuild import collect_physics_subroutines, import_config, gather_variable_definitions
#from mkcap import CapsMakefile, CapsCMakefile, CapsSourcefile, \
#                  SchemesMakefile, SchemesCMakefile, SchemesSourcefile, \
#                  TypedefsMakefile, TypedefsCMakefile, TypedefsSourcefile
#from mkdoc import metadata_to_html, metadata_to_latex
from mkstatic import API, Suite, Group
from parse_checkers import registered_fortran_ddt_names

###############################################################################
# Set up the command line argument parser and other global variables          #
###############################################################################

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--sdf',           action='store', help='suite definition file to use', required=True)
parser.add_argument('-m', '--metadata_path', action='store', help='path to CCPP scheme metadata files', required=True)
parser.add_argument('-c', '--config',        action='store', help='path to CCPP prebuild configuration file', required=True)
parser.add_argument('-v', '--variable',      action='store', help='remove files created by this script, then exit', required=True)
parser.add_argument('--debug',               action='store_true', help='enable debugging output', default=False)
args = parser.parse_args()

###############################################################################
# Functions and subroutines                                                   #
###############################################################################

def parse_arguments(args):
    """Parse command line arguments."""
    success = True
    sdf = args.sdf
    var = args.variable
    configfile = args.config
    metapath = args.metadata_path
    debug = args.debug
    return(success,sdf,var,configfile,metapath,debug)

def setup_logging(debug):
    """Sets up the logging module and logging level."""
    success = True
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)
    if debug:
        logging.info('Logging level set to DEBUG')
    else:
        logging.info('Logging level set to INFO')
    return success

def parse_suite(sdf):
    """Reads provided sdf, parses ordered list of schemes for the suite specified by said sdf"""
    print('reading sdf ' + sdf)
    suite = Suite(sdf_name=sdf)
    success = suite.parse()
    if not success:
        logging.error('Parsing suite definition file {0} failed.'.format(sdf))
        success = False
        return
    print('Successfully read sdf' + suite.sdf_name)
    print('reading list of schemes from suite ' + suite.name)
    print('creating calling tree of schemes')
    success = suite.make_call_tree()
    print(suite.call_tree)
    if not success:
        logging.error('Parsing suite definition file {0} failed.'.format(sdf))
        success = False
        return
    return (success, suite)

def create_metadata_filename_dict(metapath):
    """Given a path, read all .meta files and add them to a dictionary with their associated schemes"""

    success = True
    scheme_filenames=glob.glob(metapath + "*.meta")
    metadata_dict = {}
    print(scheme_filenames)

    for scheme_fn in scheme_filenames:
        schemes=find_scheme_names(scheme_fn)
        # The above returns a list of schemes in each filename, but we want a dictionary of schemes associated with filenames:
        for scheme in schemes:
            metadata_dict[scheme]=scheme_fn

    return (metadata_dict, success)


def create_var_graph(suite, var, config, metapath):
    """Given a suite, variable name, and a 'config' dictionary:
         1. Loops through the call tree of provided suite
         2. For each scheme, reads .meta file for said scheme, checks for variable within that scheme, and if it exists, adds an entry to an ordered dictionary with the name of the scheme and the intent of the variable"""

    success = True

    # Create an ordered dictionary that will hold the in/out information for each scheme
    var_graph=collections.OrderedDict()

    logging.debug("reading .meta files in path:\n {0}".format(metapath))
    (metadata_dict, success)=create_metadata_filename_dict(metapath)

    print(metadata_dict)

    logging.debug("reading metadata files for schemes defined in config file:\n {0}".format(config['scheme_files']))

    # Loop through call tree, find matching filename for scheme via dictionary schemes_in_files, 
    # then parse that metadata file to find variable info
    for scheme in suite.call_tree:
        logging.debug("reading meta file for scheme {0} ".format(scheme))

        if scheme in metadata_dict:
            scheme_filename = metadata_dict[scheme]
        else:
            raise Exception("Error, scheme '{0}' from suite '{1}' not found in metadata files in {2}".format(scheme, suite.sdf_name, metapath))

        logging.debug("reading metadata file {0} for scheme {1}".format(scheme_filename, scheme))

        #(metadata_from_scheme, _) = read_new_metadata(scheme_filename, module_name, table_name)
        new_metadata_headers = parse_metadata_file(scheme_filename, known_ddts=registered_fortran_ddt_names(), logger=logging.getLogger(__name__))
        for scheme_metadata in new_metadata_headers:
            for section in scheme_metadata.sections():
                found_var = []
                intent = None
                for scheme_var in section.variable_list():
#                    print(scheme_var.get_prop_value('standard_name'))
                    exact_match = False
                    if var == scheme_var.get_prop_value('standard_name'):
                        logging.debug("Found variable {0} in scheme {1}\n".format(var,section.title))
                        exact_match = True
                        found_var = var
                        intent = scheme_var.get_prop_value('intent')
                        break
                    else:
                        scheme_var_standard_name = scheme_var.get_prop_value('standard_name')
                        if scheme_var_standard_name.find(var) != -1:
#                            print("{0} matches {1}\n".format(var, scheme_var_standard_name))
                            found_var.append(scheme_var_standard_name)
#                        else:
#                            print("{0} does not match {1}\n".format(var, scheme_var_standard_name))
                if not found_var:
                    print("Did not find variable {0} in scheme {1}\n".format(var,section.title))
                elif exact_match:
                    print("Exact match found for variable {0} in scheme {1}, intent {2}\n".format(var,section.title,intent))
                else:
                    print("Found inexact matches for variable(s) {0} in scheme {1}:\n".format(var,section.title))
                    print(found_var)

    print('found variable ' + args.variable + ' in [scheme], adding scheme to list [list]')
    return (success,var_graph) 

def check_var():
    """Check given variable against standard names"""
    # This function may ultimately end up being unnecessary
    success = True
    print('Checking if ' + args.variable + ' is in list of standard names')
    return success

def main():
    """Main routine that traverses a CCPP scheme and outputs the list of schemes that modify given variable"""

    (success, sdf, var, configfile, metapath, debug) = parse_arguments(args)
    if not success:
        raise Exception('Call to parse_arguments failed.')

    success = setup_logging(debug)
    if not success:
        raise Exception('Call to setup_logging failed.')

#    success = check_var()
#    if not success:
#        raise Exception('Call to check_var failed.')

    (success, suite) = parse_suite(sdf)
    if not success:
        raise Exception('Call to parse_suite failed.')

    (success, config) = import_config(configfile, None)
    if not success:
        raise Exception('Call to import_config failed.')

    # Variables defined by the host model
    (success, metadata_define, dependencies_define) = gather_variable_definitions(config['variable_definition_files'], config['typedefs_new_metadata'])
    if not success:
        raise Exception('Call to gather_variable_definitions failed.')

    (success, var_graph) = create_var_graph(suite, var, config, metapath)
    if not success:
        raise Exception('Call to create_var_graph failed.')

    print('For suite [suite], the following schemes (in order) modify the variable ' + var)

if __name__ == '__main__':
    main()

