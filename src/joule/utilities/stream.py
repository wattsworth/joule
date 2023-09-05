#from joule.services.parse_pipe_config import parse_inline_config

#from joule.api.data_stream import DataStream, Element


def build_stream(name, inline_config: str):# -> DataStream:
    assert(False, 'deprecated')
    s = DataStream()
    s.name = name
    (datatype, names) = parse_inline_config(inline_config)
    s.datatype = datatype.name.lower(),
    i = 0
    for name in names:
        e = Element()
        e.name = name
        e.index = i
        s.elements.append(e)
    return s
