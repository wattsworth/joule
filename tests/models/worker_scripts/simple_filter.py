import sys
import os
JOULE_PATH = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)
sys.path.append(JOULE_PATH)
from joule import FilterModule, EmptyPipe
import asyncio


class SimpleFilter(FilterModule):

    async def run(self, parsed_args, inputs, outputs):
        # input1 ----( *2 )---> output1
        input1 = inputs['input1']
        output1 = outputs['output1']
        # input2 ----( *3 )---> output2
        input2 = inputs['input2']
        output2 = outputs['output2']
        while not input1.is_empty():
            data = await input1.read()
            input1.consume(len(data))
            data['data'] *= 2.0
            await output1.write(data)
            if input1.end_of_interval:
                await output1.close_interval()
        while True:
            try:
                data = await input2.read()
                input2.consume(len(data))
                data['data'] *= 3.0
                await output2.write(data)
                if input2.end_of_interval:
                    await output2.close_interval()
            except EmptyPipe:
                break
        # delay so worker output handler has time to process
        # the results
        await output1.close()
        await output2.close()
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    my_filter = SimpleFilter()
    my_filter.start()
