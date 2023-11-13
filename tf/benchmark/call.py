#!/usr/bin/env python3

"""
Call a lambda function
"""

import argparse
import json
import boto3

client = boto3.client('lambda')

parser = argparse.ArgumentParser()
parser.add_argument('name', type=str, help='name of the function to call')
# parser.add_argument('-s', '--size', type=int, required=True)
# parser.add_argument('-n', '--number', type=int, default=1)
args = parser.parse_args()

input = {}

response = client.invoke(
    FunctionName=args.name,
    InvocationType='RequestResponse',
    Payload=json.dumps(input),
)

response = json.loads(response['Payload'].read().decode('utf-8'))

print(response)
