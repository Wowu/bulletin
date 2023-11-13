import time
import os
from bulletin import EFSCommunicator, AutoCommunicator, BulletinConfig, BulletinRule, DynamoDBCommunicator

EFS_MOUNT = "/mnt/efs"

def lambda_handler(event, context) -> dict:
    if event["role"] == "exec":
        return {
            "output": os.popen(event["command"]).read()
        }

    if "auto" in event and event["auto"] == True:
        communicator = AutoCommunicator(BulletinConfig(config={
            's3': {
                'bucket': "benchmark-s3-0djr1057"
            },
            'dynamodb': {
                'table': "benchmark-s3-tk9ruvd0"
            },
            'efs': {
                'mount_path': EFS_MOUNT
            },
        }, rules=[
            # BulletinRule(method='dynamodb', vpc=None, fully_serverless=None, event_size={"less_than_or_eq": 400_000}),
            # BulletinRule(method='s3', vpc=None, fully_serverless=None, event_size={"greater_than": 400_000}),
            BulletinRule(method='dynamodb', vpc=None, fully_serverless=None, event_size=None),
        ]), vpc=True, fully_serverless=True)
    else:
        communicator = EFSCommunicator(mount_path=EFS_MOUNT)

    start = time.time()

    key = event["key"]
    role = event["role"]

    if role == "sender":
        message_length = event["message_length"]
        message = b"a" * message_length
        communicator.send(key, message)
        if "auto" in event and event["auto"] == True:
            received_message = communicator.receive(key+"-response", expected_size=message_length)
        else:
            received_message = communicator.receive(key+"-response")

        if received_message != message:
            raise ValueError(f"different messages: {received_message} != {message}")

    elif role == "receiver":
        if "auto" in event and event["auto"] == True:
            message = communicator.receive(key, expected_size=event["message_length"])
        else:
            message = communicator.receive(key)
        communicator.send(key+"-response", message)

    total_time = time.time() - start

    # cleanup
    if role == "sender":
        communicator.cleanup(key+"-response")
    elif role == "receiver":
        communicator.cleanup(key)

    return {
        "start": start,
        "key": key,
        "total_time": total_time,
        "role": role,
        "message_length": len(message),
        "usage": communicator.usage,
    }
