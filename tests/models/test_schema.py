import unittest
from joule.models import (Element, DataStream, Folder)


class TestSchema(unittest.TestCase):
    def test_relationships(self):
        # root
        #  -folder1
        #     -stream11 (4 elements)
        #  -folder2
        #     -stream21 (2 elements)
        #  -stream1 (1 element)
        #  -stream2 (1 element)

        stream11 = DataStream(name="stream11", datatype=DataStream.DATATYPE.FLOAT32)
        stream11.elements = [Element(name="e%d" % x,
                                     display_type=Element.DISPLAYTYPE.DISCRETE) for x in range(4)]
        folder1 = Folder(name="folder1")
        folder1.data_streams.append(stream11)

        stream21 = DataStream(name="stream21", datatype=DataStream.DATATYPE.UINT8)
        stream21.elements = [Element(name="e%d" % x,
                                     display_type=Element.DISPLAYTYPE.CONTINUOUS) for x in range(4)]
        folder2 = Folder(name="folder2")
        folder2.data_streams.append(stream21)

        stream1 = DataStream(name="stream1", datatype=DataStream.DATATYPE.INT8)
        stream1.elements.append(Element(name="e0"))

        stream2 = DataStream(name="stream2", datatype=DataStream.DATATYPE.UINT64)
        stream2.elements.append(Element(name="e0"))

        root = Folder(name="root")
        root.children = [folder1, folder2]
        root.data_streams = [stream1, stream2]
        # check downward navigation
        self.assertEqual(len(root.children[0].data_streams[0].elements), 4)
        # check upward navigation
        e = stream11.elements[-1]
        self.assertEqual(e.stream.folder.parent.name, 'root')
