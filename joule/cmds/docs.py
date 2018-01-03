
from cliff.command import Command
import shlex
import json
import subprocess
import re
import textwrap
import markdown
from bs4 import BeautifulSoup

from . import helpers


class DocsCmd(Command):
    "Manage the Joule Module documentation repository"

    def __init__(self, app, app_args, cmd_name=None):
        super(DocsCmd, self).__init__(app, app_args, cmd_name)

    def get_parser(self, prog_name):
        parser = super(DocsCmd, self).get_parser(prog_name)
        parser.add_argument('--config-file', dest="config_file")
        actions = ["add", "update", "list", "delete"]
        parser.add_argument('actions', choices=actions)
        parser.add_argument('value', required=False)
        return parser

    def take_action(self, parsed_args):
        configs = helpers.parse_config_file(parsed_args.config_file)
        try:
            # read module docs in from file
            with open(configs.jouled.module_doc, 'r') as data_file:
                module_docs = json.load(data_file)
                
            # [list]: display names of documented modules
            if(parsed_args.action == "list"):
                self.show_docs(module_docs)
                return
            # [delete]: remove module doc by name
            if(parsed_args.action == "delete"):
                self.remove_doc(module_docs, parsed_args.value)
                return
            
            help_output = self.get_help_output(parsed_args.value)
            raw_doc = self.parsed_help_output(help_output)
            html_doc = self.markdown_values(raw_doc)
            self.validate_doc(html_doc)

            # [add]: insert a new module doc
            if(parsed_args.action == "add"):
                self.insert_doc(module_docs, html_doc)
            # [update]: update an existing module doc
            if(parsed_args.action == "update"):
                self.update_doc(module_docs, html_doc)

            # save the module doc back out to file
            with open(configs.jouled.module_doc, 'w') as data_file:
                json.dump(module_docs, data_file)
                
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print("Error invoking [%s -h]: %s" %
                  (parsed_args.exec_cmd, str(e)))
            return 1
        except Exception as e:
            print("Error: %s" % str(e))
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

    def markdown_values(self, item):
        for key in item:
            item[key] = markdown.markdown(item[key],
                                          extensions=
                                          ['markdown.extensions.extra'])
        if("stream_configs" not in item):
            raise Exception(":stream_configs: is required")
        soup = BeautifulSoup(item["stream_configs"], 'html.parser')
        stream_configs = {}
        for d in list(zip(soup.find_all("dt"), soup.find_all("dd"))):
            stream_configs[d[0].string] = textwrap.dedent(d[1].string)
        if(len(stream_configs) == 0):
            raise Exception("invalid :stream_configs:")
        item["stream_configs"] = stream_configs
        return item

    def validate_doc(self, item):
        req_keys = ["name",
                    "exec_cmd",
                    "module_config",
                    "stream_configs"]
        for k in req_keys:
            if(k not in item):
                raise Exception(":%s: is required" % k)
        # make sure stream_configs is a dictionary
        
    def insert_doc(self, collection, item):
        # insert the item into the collection
        # raise error if item exists in collection
        for x in collection:
            if(x["name"] == item["name"]):
                raise Exception("[%s] is already documented" +
                                " specify -u to update")
        collection.append(item)

    def update_doc(self, collection, item):
        # update the item in the collection
        # raise error if item does not exist
        for i in range(len(collection)):
            if(collection[i]["name"] == item["name"]):
                collection[i] = item
                return
            
        raise Exception("[%s] is not documented" +
                        " specify -a to add")

    def list_docs(self, collection):
        # display list of modules by name
        print("Documented modules")
        for item in collection:
            print("\t%s" % item["name"])

    def remove_doc(self, collection, name):
        for i in range(len(collection)):
            if(collection[i]["name"] == name):
                del collection[i]
                return
        raise Exception("[%s] is not documented")
        
