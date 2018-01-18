from joule.daemon import module, stream, element


def build_stream(name="stream", description="",
                 path="/default/path", keep_us=0,
                 datatype="float32", decimate=False, num_elements=4):
    my_stream = stream.Stream(name, description, path,
                              datatype, keep_us, decimate)
    for i in range(num_elements):
        my_stream.elements.append(element.build_element(
            name="{:s}_s{:d}".format(name, i)))
    return my_stream


def build_module(name="module", description="", exec_cmd="/bin/true",
                 output_paths=None,
                 input_paths=None):
    if(output_paths is None):
        output_paths = {}
    if(input_paths is None):
        input_paths = {}
    m = module.Module(name, description, exec_cmd,
                      input_paths, output_paths)
    m.output_paths = output_paths
    m.input_paths = input_paths
    return m


def assertUnorderedListEqual(fixture, a, b):
    a.sort()
    b.sort()
    fixture.assertListEqual(a, b)
