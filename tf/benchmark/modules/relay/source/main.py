import time
import os
from bulletin import RelayCommunicator

SERVER_IP = os.environ["SERVER_IP"]

def lambda_handler(event, context) -> dict:
    communicator = RelayCommunicator(host=SERVER_IP)

    start = time.time()

    key = event["key"]
    role = event["role"]

    if role == "sender":
        message_length = event["message_length"]
        message = b"a" * message_length
        communicator.send(key, message)
        received_message = communicator.receive(key+"-response")

        if received_message != message:
            raise ValueError("different messages")

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
