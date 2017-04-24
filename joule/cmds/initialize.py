
from cliff.command import Command
import pkg_resources
import shutil
import os
import sys


class InitializeCmd(Command):
    "Setup joule configuration files in default location"

    def take_action(self, parsed_args):

        sys.stdout.write("1. creating joule user ")
        r = os.system("useradd -r -G dialout joule")
        code = r >> 8
        if(code == 0):
            print("[OK]")
        elif(code == 1):
            print("[ERROR]\n run as [sudo joule initialize]")
            exit(1)
        elif(code == 9):
            print("[exists]")
        else:
            print("[ERROR]\n unknown error [%d] see [man useradd]" % r)
            exit(1)
        print("registering system service")
        service_file = pkg_resources.resource_filename(
            "joule", "resources/jouled.service")
        shutil.copy(service_file, "/tmp/")

        print("2. copying configuration to /etc/joule ")
        self.make_joule_directory("/etc/joule")
        # check if main.conf exists
        if(not os.is_file("/etc/joule/main.conf")):
            conf_file = pkg_resources.resource_filename(
                "joule", "resources/templates/main.conf")
            shutil.copy(conf_file, "/etc/joule")
        # set ownership to joule user
        shutil.chown("/etc/joule/main.conf", user="joule", group="joule")

        # setup stream config directory
        self.make_joule_directory("/etc/joule/stream_configs")
        example_file = pkg_resources.resource_filename(
                "joule", "resources/templates/stream.example")
        shutil.copy(example_file, "/etc/joule/stream_configs")
        # set ownership to joule user
        shutil.chown("/etc/joule/stream_configs/stream.example",
                     user="joule", group="joule")

        # setup module config directory
        self.make_joule_directory("/etc/joule/module_configs")
        example_file = pkg_resources.resource_filename(
                "joule", "resources/templates/module.example")
        shutil.copy(example_file, "/etc/joule/module_configs")
        # set ownership to joule user
        shutil.chown("/etc/joule/module_configs/module.example",
                     user="joule", group="joule")
        print("[OK]")

    def make_joule_directory(path):
        # check if directory exists
        if(not os.is_dir(path)):
            os.mkdir("/etc/joule")
        # set ownership to joule user
        shutil.chown(path, user="joule", group="joule")
    
