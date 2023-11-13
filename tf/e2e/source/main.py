import os
import time
import pickle
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
print("starting to import tensorflow")
from tensorflow.keras.datasets import mnist
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import SGD
from tensorflow.keras.utils import to_categorical
import numpy as np
import pandas as pd

from bulletin import S3Communicator, EFSCommunicator, DynamoDBCommunicator, RedisCommunicator, RelayCommunicator, P2PCommunicator, AutoCommunicator, BulletinConfig, BulletinRule
print("end of imports")

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
EFS_MOUNT = "/mnt/efs"
# REDIS_IP = os.environ["REDIS_IP"]
# RELAY_IP = os.environ["RELAY_IP"]
# P2P_IP = os.environ["P2P_IP"]


def trace(name):
    global events, rank
    events.append({
        "name": name,
        "rank": rank,
        "time": time.time()
    })


def log(msg):
    global rank
    print(f"[{rank}] {msg}")


def load_data():
    # Load the MNIST dataset
    (X_train, y_train), (X_test, y_test) = mnist.load_data()
    # Flatten and normalize input images
    X_train = X_train.reshape((X_train.shape[0], 28 * 28)) / 255.0
    X_test = X_test.reshape((X_test.shape[0], 28 * 28)) / 255.0
    # Convert the labels to one-hot encoding
    y_train = to_categorical(y_train)
    y_test = to_categorical(y_test)
    return X_train, y_train, X_test, y_test


def create_model():
    # Create a sequential model
    model = Sequential()
    # Add a fully connected layer
    model.add(Dense(128, activation='relu', input_shape=(28 * 28,)))
    # Add the output layer
    model.add(Dense(10, activation='softmax'))
    # Compile the model with optimizer
    model.compile(
        optimizer=SGD(learning_rate=0.01),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model


def calc_weight_diff(weights_before, weights_after):
    w1 = weights_after[0] - weights_before[0]
    b1 = weights_after[1] - weights_before[1]
    w2 = weights_after[2] - weights_before[2]
    b2 = weights_after[3] - weights_before[3]

    return [w1, b1, w2, b2]


def apply_weight_diff(weights, weight_diff):
    return [
        weights[0] + weight_diff[0],
        weights[1] + weight_diff[1],
        weights[2] + weight_diff[2],
        weights[3] + weight_diff[3],
    ]


def average_weight_diff(weight_diffs):
    w1 = [w[0] for w in weight_diffs]
    b1 = [w[1] for w in weight_diffs]
    w2 = [w[2] for w in weight_diffs]
    b2 = [w[3] for w in weight_diffs]

    return [
        np.mean(w1, axis=0),
        np.mean(b1, axis=0),
        np.mean(w2, axis=0),
        np.mean(b2, axis=0),
    ]


def create_communicator():
    global method, communicators

    # return existing communicator due to errors with boto3
    # credential gathering
    if len(communicators) > 0 and method in ['s3', 'dynamodb', 'auto']:
        return list(communicators.values())[0]

    if method == 's3':
        return S3Communicator(S3_BUCKET_NAME)
    elif method == 'dynamodb':
        return DynamoDBCommunicator(DYNAMODB_TABLE_NAME)
    elif method == 'efs':
        return EFSCommunicator(mount_path=EFS_MOUNT)
    elif method == 'redis':
        return RedisCommunicator(REDIS_IP)
    elif method == 'relay':
        return RelayCommunicator(RELAY_IP)
    elif method == 'p2p':
        return P2PCommunicator(P2P_IP)
    elif method == 'auto':
        return AutoCommunicator(BulletinConfig(config={
            's3': {
                'bucket': S3_BUCKET_NAME
            },
            'dynamodb': {
                'table': DYNAMODB_TABLE_NAME
            },
            'efs': {
                'mount_path': EFS_MOUNT
            },
        }, rules=[
            BulletinRule(method='dynamodb', vpc=None, fully_serverless=None, event_size={"less_than_or_eq": 400_000}),
            BulletinRule(method='s3', vpc=None, fully_serverless=None, event_size={"greater_than": 400_000}),
        ]), vpc=True, fully_serverless=True)
    else:
        raise Exception("Invalid communication method")


def send(recipient, key, data):
    # check if has key in communicators
    if recipient not in communicators:
        communicators[recipient] = create_communicator()

    communicator = communicators[recipient]
    communicator.send(key, pickle.dumps(data))


def receive(sender, key):
    if sender not in communicators:
        communicators[sender] = create_communicator()

    communicator = communicators[sender]
    if isinstance(communicator, AutoCommunicator):
        data = pickle.loads(communicator.receive(key, expected_size=400_000))
    else:
        data = pickle.loads(communicator.receive(key))

    if not isinstance(communicator, RelayCommunicator) and not isinstance(communicator, P2PCommunicator):
        # communicator.cleanup(key)
        pass

    return data


def start_and_join(threads):
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]


def master_broadcast(data):
    log("master_broadcast")
    global communicators, rank, key, count, nth_comm
    nth_comm += 1

    if rank == 0:
        # threads = []
        # for i in range(1, count):
        #     threads.append(
        #         Thread(
        #             target=send,
        #             args=(f"{key}-{i}", f"{key}-{i}-{nth_comm}", data)
        #         )
        #     )
        # start_and_join(threads)
        send(f"{key}-1", f"{key}-{nth_comm}", data)
        return data
    else:
        return receive(f"{key}-0", f"{key}-{nth_comm}")


def master_gather(data):
    log("master_gather")
    global communicator, rank, key, count, nth_comm
    nth_comm += 1

    if rank == 0:
        data = []
        # for i in range(1, count):
        #     data.append(receive(f"{key}-{i}", f"{key}-{i}-{nth_comm}"))
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(receive, f"{key}-{i}", f"{key}-{i}-{nth_comm}") for i in range(1, count)]
            for future in futures:
                data.append(future.result())
        return data
    else:
        send(f"{key}-0", f"{key}-{rank}-{nth_comm}", data)
        return []


key = None
rank = None
count = None
communicators = None
events = None
nth_comm = None
method = None

def lambda_handler(event, _context) -> dict:
    # Reset
    global key, rank, count, communicators, events, nth_comm, method

    if 'code' in event:
        exec(event['code'])
        return {'ok': True}

    # Set params
    key = event['key']
    rank = event['rank']
    count = event['count']
    method = event['method']
    events = []
    epochs = event.get('epochs', 5)
    nth_comm = 0
    worker_count = count - 1
    communicators = {}

    # Init communicator once to avoid doing it multiple times
    if method in ['s3', 'dynamodb', 'auto']:
        create_communicator()

    print(f"rank={rank} count={count} key={key}")

    history = []

    # #
    # # Start
    # #

    print("download data")
    X_train, y_train, X_test, y_test = load_data()
    print("data downloaded")

    start = time.time()

    model = create_model()

    for _ in range(epochs):
        # Sync weights
        weights = model.get_weights()
        weights = master_broadcast(weights)
        model.set_weights(weights)
        # At this point each worker has the same weights
        log("Synced weights")

        if rank == 0:
            weight_diff = None
        else:
            weights_before = model.get_weights()
            worker_id = rank - 1
            model.fit(
                X_train[worker_id::worker_count],
                y_train[worker_id::worker_count],
                epochs=1,
                batch_size=128
            )
            weights_after = model.get_weights()
            weight_diff = calc_weight_diff(weights_before, weights_after)

        weight_diffs = master_gather(weight_diff)
        log("Gathered weight diffs")

        if rank == 0:
            avgd = average_weight_diff(weight_diffs)
            model.set_weights(apply_weight_diff(model.get_weights(), avgd))

            history.append(model.evaluate(X_test, y_test, return_dict=True))

    # Close sockets
    for communicator in communicators.values():
        if communicator is RelayCommunicator or communicator is P2PCommunicator:
            communicator.cleanup()

    return {
        'key': key,
        'rank': rank,
        'count': count,
        'dataset': 'mnist',
        'epochs': epochs,
        'method': method,
        # 'history': history,
        'usage': communicator.usage,
        'time': time.time() - start,
    }

    # # # Simple benchmark

    # import random

    # for i in range(epochs):
    #     a = random.randint(0, 100)
    #     a = master_broadcast(a)
    #     print(a)

    #     b = random.randint(0, 100)
    #     bs = master_gather(b)
    #     print(bs)

    # return {
    #     'key': key,
    #     'rank': rank,
    #     'count': count,
    #     'dataset': 'mnist',
    #     'epochs': 2,
    #     'method': method,
    #     # 'history': history,
    #     # 'usage': communicator.usage,
    #     'time': time.time() - start,
    # }
