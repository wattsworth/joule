
import argparse
import sys
import os
import configparser

from joule.daemon import module

""" helpers for handling module arguments
    Complicated because we want to look for module_config
    and add these args but this should be transparent
    (eg, the -h flag should show the real help)
"""


# parser for boolean args

def yesno(val):
    if(val is None):
        raise ValueError("must be 'yes' or 'no'")
    # standardize the string
    val = val.lower().rstrip().lstrip()
    if(val == "yes"):
        return True
    elif(val == "no"):
        return False
    else:
        raise ValueError("must be 'yes' or 'no'")

    
def module_args():
    # build a dummy parser to look for module_config
    temp_parser = argparse.ArgumentParser()
    temp_parser.add_argument("--module_config", default="unset")
    arg_list = sys.argv[1:]   # ignore the program name
    stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        args = temp_parser.parse_known_args()[0]
        if(args.module_config != "unset"):
            arg_list += _append_args(args.module_config)
    except SystemExit:
        pass
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    return arg_list


def _append_args(module_config_file):
    # if a module_config is specified add its args
    module_config = configparser.ConfigParser()
    with open(module_config_file, 'r') as f:
        module_config.read_file(f)
    parser = module.Parser()
    my_module = parser.run(module_config)
    return my_module.args
