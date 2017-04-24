
from cliff.command import Command
import pkg_resources
import shutil
import os
import sys



ESC_SEQ="\x1b["
COL_RESET=ESC_SEQ+"0m"
COL_RED=ESC_SEQ+"6;30;41m"
COL_GREEN=ESC_SEQ+"6;30;42m"
COL_YELLOW=ESC_SEQ+"6;30;43m"
COL_BLUE=ESC_SEQ+"34;01m"
COL_MAGENTA=ESC_SEQ+"35;01m"
COL_CYAN=ESC_SEQ+"36;01m"

class InitializeCmd(Command):
    "Setup joule configuration files in default location"

    def take_action(self, parsed_args):
        sys.stdout.write("1. creating joule user ")
        r = os.system("useradd -r -G dialout joule")
        code = r >> 8
        if(code == 0):
            print("["+COL_GREEN+"OK"+COL_RESET+"]")
        elif(code == 1):
            self.run_as_root()
        elif(code == 9):
            print("["+COL_YELLOW+"exists"+COL_RESET+"]")
        else:
            print("["+COL_RED+"ERROR"+COL_RESET+"]\n unknown error [%d] see [man useradd]" % r)
            exit(1)
        sys.stdout.write("2. registering system service ")
        service_file = pkg_resources.resource_filename(
            "joule", "resources/jouled.service")
        try:
            shutil.copy(service_file, "/etc/systemd/system")
            os.system("systemctl enable jouled.service")
            os.system("systemctl start jouled.service")
        except(PermissionError):
            self.run_as_root()
        
        print("["+COL_GREEN+"OK"+COL_RESET+"]")
        
        sys.stdout.write("3. copying configuration to /etc/joule ")
        self.make_joule_directory("/etc/joule")
        # check if main.conf exists
        if(not os.path.isfile("/etc/joule/main.conf")):
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
        print("["+COL_GREEN+"OK"+COL_RESET+"]")

    def make_joule_directory(self, path):
        try:
            # check if directory exists
            if(not os.path.isdir(path)):
                os.mkdir(path)
            # set ownership to joule user
            shutil.chown(path, user="joule", group="joule")
        except(PermissionError):
            self.run_as_root
            
    def run_as_root(self):
        print("["+COL_RED+"ERROR"+COL_RESET+"]\n run as [sudo joule initialize]")
        exit(1)
