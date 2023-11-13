#!/usr/bin/env python3
import argparse
import json
import time
import sys
import os
from threading import Thread

import boto3

client = boto3.client('lambda')


class Benchmark:
    name: str
    function_name: str
    results: list[dict] = []

    def __init__(self, name, function_name):
        self.name = name
        self.function_name = function_name

    def run(self, message_size: int, auto: bool = False):
        self.results = []

        key = os.urandom(16).hex()
        input1 = {'key': key, 'message_length': message_size, 'role': 'sender'}
        input2 = {'key': key, 'message_length': message_size, 'role': 'receiver'}

        if auto:
            input1['auto'] = True
            input2['auto'] = True

        # invoke two functions at the same time and wait for both to finish
        t1 = Thread(target=self.invoke, args=(input1,))
        t2 = Thread(target=self.invoke, args=(input2,))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        if len(self.results) != 2:
            return

        sender_results = [r for r in self.results if r['role'] == 'sender'][0]
        receiver_results = [r for r in self.results if r['role'] == 'receiver'][0]

        return {
            'receiver_start_delay': receiver_results['start'] - sender_results['start'],
            'total_time': sender_results['total_time'],
            'message_size': message_size,
            'sender_usage': sender_results['usage'],
            'receiver_usage': receiver_results['usage'],
        }

    def invoke(self, input):
        response = client.invoke(
            FunctionName=self.function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(input),
        )

        payload = json.loads(response['Payload'].read().decode('utf-8'))

        if 'errorMessage' in payload:
            print(f"error: {payload['errorMessage']}", file=sys.stderr)
            print(payload, file=sys.stderr)
        else:
            self.results.append(payload)


class Terraform:
    def download(self):
        print("Updating terraform output...")
        os.system("terraform output -json > output.json")

    def get_contents(self):
        with open("output.json", "r") as f:
            return json.load(f)

    def output(self):
        if not os.path.exists("output.json"):
            self.download()

        # check if file is older than 1 hour
        if os.path.getmtime("output.json") < time.time() - 60 * 60:
            self.download()

        return self.get_contents()


class Main:
    benchmarks: list[Benchmark]
    name: str
    message_size: int
    number: int
    auto: bool

    def __init__(self, name, message_size, number, auto: bool):
        self.name = name
        self.benchmarks = []
        self.message_size = message_size
        self.number = number
        self.auto = auto

        # load benchmarks
        output = Terraform().output()
        for name, value in output.items():
            if name.startswith("benchmark_"):
                self.benchmarks.append(Benchmark(name[len("benchmark_"):], value["value"]))

        # check if benchmark exists
        if args.name not in [b.name for b in self.benchmarks]:
            print(f"benchmark '{args.name}' not found")
            print("available benchmarks:")
            for b in self.benchmarks:
                print(f"  {b.name}")
            exit(1)

    def run(self):
        benchmark = next(b for b in self.benchmarks if b.name == self.name)

        for i in range(self.number):
            result = benchmark.run(message_size=self.message_size, auto=self.auto)
            if result:
                print(json.dumps(result))


parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('-s', '--size', type=int, required=True)
parser.add_argument('-n', '--number', type=int, default=1)
parser.add_argument('-a', '--auto', action='store_true')
args = parser.parse_args()

Main(name=args.name, message_size=args.size, number=args.number, auto=args.auto).run()
