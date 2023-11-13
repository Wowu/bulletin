import json
import uuid
import boto3
from pprint import pprint
from threading import Thread
import argparse

client = boto3.client('lambda')
function_name = "e2e-ml-ucgg8zfn"


def invoke(input, second=False):
    response = client.invoke(
        FunctionName=(function_name+"-2" if second else function_name),
        InvocationType='RequestResponse',
        Payload=json.dumps(input),
    )

    payload = json.loads(response['Payload'].read().decode('utf-8'))
    # print(f"== rank: {input.get('rank', None)}")
    print(json.dumps(payload))


parser = argparse.ArgumentParser()
parser.add_argument('--method', type=str)
parser.add_argument('--code', type=str)
parser.add_argument('--count', type=int, default=3)
parser.add_argument('--no-vpc', action='store_true')
args = parser.parse_args()

threads = []
count = args.count
method = args.method
key = uuid.uuid4().hex

if args.code:
    for i in [0]: #range(count):
        threads.append(
            Thread(target=invoke, args=({'code': args.code}, args.no_vpc,))
        )
    [t.start() for t in threads]
    [t.join() for t in threads]
    exit(0)

if not args.method:
    print("Missing --method or --code")
    exit(1)

for i in range(count):
    threads.append(
        Thread(
            target=invoke,
            args=({
                'key': key,
                'rank': i,
                'method': method,
                'count': count,
            }, args.no_vpc,)
        )
    )

[t.start() for t in threads]
[t.join() for t in threads]
