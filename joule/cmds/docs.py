
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
        actions = ["add", "update", "list", "remove"]
        parser.add_argument('action', choices=actions)
        parser.add_argument('value', nargs='?', default="")
        return parser

    def take_action(self, parsed_args):
        try:
            configs = helpers.parse_config_file(parsed_args.config_file)
            # read module docs in from file
            with open(configs.jouled.module_doc, 'r') as data_file:
                module_docs = json.load(data_file)
                
            # [list]: display names of documented modules
            if(parsed_args.action == "list"):
                self.list_docs(module_docs)
                return
            # [remove]: remove module doc by name
            if(parsed_args.action == "remove"):
                self.remove_doc(module_docs, parsed_args.value)
                print("removed documentation for [%s]" % parsed_args.value)
                with open(configs.jouled.module_doc, 'w') as data_file:
                    json.dump(module_docs, data_file, indent=4, sort_keys=True)
                return
            
            help_output = self.get_help_output(parsed_args.value)
            raw_doc = self.parse_help_output(help_output)
            html_doc = self.markdown_values(raw_doc)
            self.validate_doc(html_doc)

            # [add]: insert a new module doc
            if(parsed_args.action == "add"):
                self.insert_doc(module_docs, html_doc)
                print("added documentation for [%s]" % html_doc['name'])
                      
            # [update]: update an existing module doc
            if(parsed_args.action == "update"):
                self.update_doc(module_docs, html_doc)
                print("updated documentation for [%s]" % html_doc['name'])
                      
            # save the module doc back out to file
            with open(configs.jouled.module_doc, 'w') as data_file:
                json.dump(module_docs, data_file, indent=4, sort_keys=True)

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print("Error invoking [%s -h]: %s" %
                  (parsed_args.value, str(e)))
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
        return self.text_to_dict(text,
                                 section_marker="---",
                                 delimiter=":")
        
    def text_to_dict(self, text,
                     section_marker=None,
                     delimiter=":"):
        # return json dictionary of help output
        # find :keys: between start and end marks (---)
        # populate dictionary with [values] between :keys:
        #
        SECTION_MARKER = "---"
        res = {}
        cur_key = ""
        cur_value = ""
        in_help_section = False
        regex = "^{0}(.*){0}$".format(delimiter)
        for line in text.split('\n'):

            if(section_marker is not None):
                # check for the section marker
                if(line.lstrip().rstrip() == SECTION_MARKER):
                    if(not in_help_section):
                        in_help_section = True
                        continue
                    else:
                        break  # all done
            else:
                # no section marker read whole text
                in_help_section = True
                
            if(not in_help_section):
                continue

            # check if this line is a key
            match = re.search(regex, line.rstrip().lstrip())
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

        if(cur_key != ""):
            res[cur_key] = textwrap.dedent(cur_value).rstrip()
        return res

    def markdown_values(self, item):
        plain_items = ["name", "author", "license",
                       "module_config", "stream_configs"]
        for key in item:
            if(key in plain_items):
                continue
            item[key] = markdown.markdown(item[key],
                                          extensions=
                                          ['markdown.extensions.extra'])
        if("stream_configs" not in item):
            raise Exception(":stream_configs: is required")
        dict_configs = self.text_to_dict(item["stream_configs"],
                                         delimiter="#")
        stream_configs = []
        for key in dict_configs:
            stream_configs.append({"name": key, "config": dict_configs[key]})
        if(len(stream_configs) == 0):
            raise Exception("invalid :stream_configs:")
        item["stream_configs"] = stream_configs
        return item

    def validate_doc(self, item):
        req_keys = ["name",
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
                raise Exception("[%s] is already documented" % item["name"])
        collection.append(item)

    def update_doc(self, collection, item):
        # update the item in the collection
        # raise error if item does not exist
        for i in range(len(collection)):
            if(collection[i]["name"] == item["name"]):
                collection[i] = item
                return
            
        raise Exception("[%s] is not documented")

    def list_docs(self, collection):
        # display list of modules by name
        if(len(collection) == 0):
            print("No documented modules")
            return
        
        print("Documented modules:")
        for item in collection:
            print("\t%s" % item["name"])

    def remove_doc(self, collection, name):
        for i in range(len(collection)):
            if(collection[i]["name"] == name):
                del collection[i]
                return
        raise Exception("[%s] is not documented" % name)
        
