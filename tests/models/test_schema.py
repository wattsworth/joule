import unittest

from joule.models import (Element, Stream, Folder)


class TestSchema(unittest.TestCase):
    def test_relationships(self):
        # root
        #  -folder1
        #     -stream11 (4 elements)
        #  -folder2
        #     -stream21 (2 elements)
        #  -stream1 (1 element)
        #  -stream2 (1 element)

        stream11 = Stream(name="stream11", datatype=Stream.DATATYPE.FLOAT32)
        stream11.elements = [Element(name="e%d" % x,
                                     type=Element.TYPE.DISCRETE) for x in range(4)]
        folder1 = Folder(name="folder1")
        folder1.streams.append(stream11)

        stream21 = Stream(name="stream21", datatype=Stream.DATATYPE.UINT8)
        stream21.elements = [Element(name="e%d" % x,
                                     type=Element.TYPE.CONTINUOUS) for x in range(4)]
        folder2 = Folder(name="folder2")
        folder2.streams.append(stream21)

        stream1 = Stream(name="stream1", datatype=Stream.DATATYPE.INT8)
        stream1.elements.append(Element(name="e0"))

        stream2 = Stream(name="stream2", datatype=Stream.DATATYPE.UINT64)
        stream2.elements.append(Element(name="e0"))

        root = Folder(name="root")
        root.children = [folder1, folder2]
        root.streams = [stream1, stream2]

        # check downward navigation
        self.assertEqual(len(root.children[0].streams[0].elements), 4)
        # check upward navigation
        e = stream11.elements[-1]
        self.assertEqual(e.stream.folder.parent.name, 'root')
