from joule import FilterModule

class Filter(FilterModule):
    def run(self, inputs, outputs):
        # read input and send it to output
        for x in range(2):  # expect 2 intervals of data
            for i in range(2):
                data = await
                inputs[i].read(flatten=True) * (i + 2.0)
                await
                outputs[i].write(data)
                self.assertEqual(len(data), 100)
                self.assertTrue(inputs[i].end_of_interval)
                await
                outputs[i].close_interval()
                inputs[i].consume(len(data))
        outputs[0].close()
        outputs[1].close()