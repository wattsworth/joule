from joule import FilterModule, EmptyPipe
import sys


class SimpleFilter(FilterModule):

    async def run(self, parsed_args, inputs, outputs):
        # input1 ----( *2 )---> output1
        input1 = inputs['input1']
        output1 = outputs['output1']
        # input2 ----( *3 )---> output2
        input2 = inputs['input2']
        output2 = outputs['output2']

        while True:
            try:
                data = await input1.read()
                input1.consume(len(data))
                data['data'] *= 2.0
                sys.stdout.flush()
                await output1.write(data)
                if input1.end_of_interval:
                    await output1.close_interval()
            except EmptyPipe:
                break
        while True:
            try:
                data = await input2.read()
                print("here!")
                input2.consume(len(data))
                data['data'] *= 3.0
                await output2.write(data)
                if input2.end_of_interval:
                    await output2.close_interval()
            except EmptyPipe:
                break


if __name__ == "__main__":
    my_filter = SimpleFilter()
    my_filter.start()
