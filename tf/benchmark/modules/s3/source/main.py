import time
import os
from bulletin import S3Communicator

BUCKET = os.environ["BUCKET_NAME"]

def lambda_handler(event, context) -> dict:
    communicator = S3Communicator(bucket=BUCKET)

    start = time.time()

    key = event["key"]
    role = event["role"]

    if role == "sender":
        message_length = event["message_length"]
        message = b"a" * message_length
        communicator.send(key, message)
        received_message = communicator.receive(key+"-response")

        if received_message != message:
            raise ValueError(f"different messages: {received_message} != {message}")

    elif role == "receiver":
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

