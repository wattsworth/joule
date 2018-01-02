
from cliff.command import Command
import shlex
import json
import subprocess
import re
import textwrap

from . import helpers


class DocsCmd(Command):
    "Manage the Joule Module documentation repository"

    def __init__(self, app, app_args, cmd_name=None):
        super(DocsCmd, self).__init__(app, app_args, cmd_name)

    def get_parser(self, prog_name):
        parser = super(DocsCmd, self).get_parser(prog_name)
        parser.add_argument('--config-file', dest="config_file")
        parser.add_argument('exec_cmd')
        return parser

    def take_action(self, parsed_args):
        configs = helpers.parse_config_file(parsed_args.config_file)
        try:
            with open(configs.jouled.module_doc, 'r') as data_file:
                module_docs = json.load(data_file)
            help_output = self.get_help_output(parsed_args.exec_cmd)
            new_doc = self.parsed_help_output(help_output)
            self.upsert(module_docs, new_doc)

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print("Error invoking [%s -h]: %s" % (parsed_args.exec_cmd, str(e)))
            return 1

    def get_help_output(self, exec_cmd):
        # run the exec command to get the module help tag
        cmd = shlex.split(exec_cmd)+['-h']
        p = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        return p.stdout.decode('utf-8')

    def parse_help_output(self, text):
        # return json dictionary of help output
        # find :keys: between start and end marks (---)
        # populate dictionary with [values] between :keys:
        #
        SECTION_MARKER = "---"
        res = {}
        cur_key = ""
        cur_value = ""
        in_help_section = False
        
        for line in text.split('\n'):
            # check for the section marker
            if(line.lstrip().rstrip() == SECTION_MARKER):
                if(not in_help_section):
                    in_help_section = True
                    continue
                else:
                    if(cur_key != ""):
                        res[cur_key] = textwrap.dedent(cur_value).rstrip()
                    break  # all done
                
            if(not in_help_section):
                continue

            # check if this line is a key
            match = re.search(r"^:(.*):$", line.rstrip().lstrip())
            if(match is not None):
                key = match.group(1)
                # save last key:value pair
                if(not cur_key == ""):
                    res[cur_key] = textwrap.dedent(cur_value).rstrip()
                # start working on the new one
                cur_key = key
                cur_value = ""
                continue

            # this is part of a value
            cur_value += line + "\n"
            
        return res

    def upsert(self, collection, item):
        # update or insert the item into the collection
        pass
