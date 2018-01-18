from joule.daemon import module


def build_module(name,
                 description="test_description",
                 exec_cmd="/bin/true",
                 input_paths={"path1": "/some/path/1"},
                 output_paths={"path1": "/some/path/2"},
                 status=module.STATUS_UNKNOWN,
                 pid=-1,
                 id=None):
    return module.Module(name, description, exec_cmd, input_paths, output_paths,
                         status=status, pid=pid, id=id)
