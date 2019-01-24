from joule.services.parse_pipe_config import parse_inline_config

from joule.api.stream import Stream, Element


def build_stream(name, inline_config: str) -> Stream:
    s = Stream()
    s.name = name
    (datatype, names) = parse_inline_config(inline_config)
    s.datatype = datatype
    i = 0
    for name in names:
        e = Element()
        e.name = name
        e.index = i
        s.elements.append(e)
    return s
