import socket
import time
import os
from abc import ABC, abstractmethod
from threading import Event, Thread
import boto3

from .p2p_utils import string_to_addr, addr_to_string, send_msg, recv_msg

MEGABYTE = 1000*1000
BUFF_SIZE = 1*MEGABYTE

class Communicator(ABC):
    events: list[str]

    def __init__(self):
        self.events = []
        self.poll_limit = 1000

    @property
    def usage(self) -> dict[str, int]:
        """Tally events"""
        event_counts = {}
        for event in self.events:
            if event not in event_counts:
                event_counts[event] = 0
            event_counts[event] += 1

        return event_counts

    @abstractmethod
    def send(self, key: str, data: bytes):
        pass

    @abstractmethod
    def receive(self, key: str) -> bytes:
        pass

    @abstractmethod
    def cleanup(self, key: str):
        pass

    def backoff_sleep(self, i):
        time.sleep(2**(i/50)/1000)


class S3Communicator(Communicator):
    bucket: str

    def __init__(self, bucket: str):
        super().__init__()
        self.bucket = bucket
        self.client = boto3.client("s3")

    def send(self, key: str, data: bytes):
        self.events.append("s3:PutObject")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def receive(self, key: str) -> bytes:
        for i in range(self.poll_limit):
            try:
                self.events.append("s3:GetObject")
                return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            except:
                self.backoff_sleep(i)

        raise TimeoutError("Exceeded poll limit while waiting for message")

    def cleanup(self, key: str):
        self.events.append("s3:DeleteObject")
        self.client.delete_object(Bucket=self.bucket, Key=key)


class EFSCommunicator(Communicator):
    mount_path: str

    def __init__(self, mount_path: str):
        super().__init__()
        self.mount_path = mount_path

    def send(self, key: str, data: bytes):
        with open(os.path.join(self.mount_path, key+"-tmp"), "wb") as f:
            self.events.append("efs:write")
            f.write(data)

        os.rename(os.path.join(self.mount_path, key+"-tmp"),os.path.join(self.mount_path, key))

    def receive(self, key: str) -> bytes:
        for i in range(self.poll_limit):
            try:
                self.events.append("efs:listdir")
                files = os.listdir(self.mount_path)
                if key in files:
                    with open(os.path.join(self.mount_path, key), "rb") as f:
                        self.events.append("efs:read")
                        data = f.read()
                        if data:
                            return data
            except:
                pass

            self.backoff_sleep(i)

        raise TimeoutError("Exceeded poll limit while waiting for message")

    def cleanup(self, key: str):
        self.events.append("efs:delete")
        os.remove(os.path.join(self.mount_path, key))


class DynamoDBCommunicator(Communicator):
    def __init__(self, table_name: str):
        super().__init__()
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)

    def send(self, key: str, data: bytes):
        self.events.append("dynamodb:PutItem")
        self.table.put_item(Item={"id": key, "message": data})

    def receive(self, key: str) -> bytes:
        for i in range(self.poll_limit):
            try:
                self.events.append("dynamodb:GetItem")
                return bytes(self.table.get_item(Key={"id": key})["Item"]["message"])
            except:
                self.backoff_sleep(i)

        raise TimeoutError("Exceeded poll limit while waiting for message")

    def cleanup(self, key: str):
        self.events.append("dynamodb:DeleteItem")
        self.table.delete_item(Key={"id": key})


class RedisCommunicator(Communicator):
    def __init__(self, host: str, port=6379):
        super().__init__()
        import redis
        self.redis = redis.Redis(host=host, port=port, db=0)

    def send(self, key: str, data: bytes):
        self.events.append("redis:set")
        self.redis.set(key, data)

    def receive(self, key: str) -> bytes:
        for i in range(self.poll_limit):
            self.events.append("redis:get")
            value = self.redis.get(key)
            if value is not None:
                return value

            self.backoff_sleep(i)

        raise TimeoutError("Exceeded poll limit while waiting for message")

    def cleanup(self, key: str):
        self.events.append("redis:delete")
        self.redis.delete(key)


class RelayCommunicator(Communicator):
    def __init__(self, host: str, port=12345):
        super().__init__()
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((host, port))

    def send(self, key: str, data: bytes):
        self._socket_send_message(self._build_message("publish", key, data))

    def receive(self, key: str) -> bytes:
        self._socket_send_message(self._build_message("subscribe", key, b""))

        message = self._socket_receive_message()
        try:
            msg = self._parse_message(message)
        except Exception as e:
            print("ERROR decoding data:", message)
            raise e

        return msg["message"]

    def cleanup(self, key: str):
        self.client.close()

    def _parse_message(self, message: bytes) -> dict:
        split = message.split(b"#", 2)
        action = split[0].decode("utf-8")
        channel = split[1].decode("utf-8")
        data = split[2]

        return {
            "action": action,
            "channel": channel,
            "message": data
        }

    def _build_message(self, action: str, channel: str, data: bytes) -> bytes:
        return action.encode('utf-8') + b"#" + channel.encode('utf-8') + b"#" + data

    def _socket_send_message(self, data: bytes):
        self.client.send(str(len(data)).rjust(16).encode("utf-8"))
        self.client.send(data)

    def _socket_receive_message(self) -> bytes:
        message = b""
        data = self.client.recv(16)

        if not data:
            return b""

        size = int(data)
        while len(message) < size:
            bytes_to_receive = min(size - len(message), BUFF_SIZE)
            data = self.client.recv(bytes_to_receive)
            message += data

        return message


class P2PCommunicator(Communicator):
    STOP: Event
    server: socket.socket
    socket: socket.socket
    host: str
    port: int

    def __init__(self, host: str, port=12345):
        super().__init__()
        self.STOP = Event()
        self.host = host
        self.port = port
        self.server = None
        self.socket = None

    def _connect(self, key: str):
        #
        # TCP hole punching
        #

        print("client start")

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.connect((self.host, self.port))
        priv_addr = self.server.getsockname()

        # 1. client->server. send client private_ip+port
        send_msg(self.server, addr_to_string(priv_addr) + b"|" + key.encode('utf-8'))
        # 4. receive our public_ip+port
        data = recv_msg(self.server)
        print("client %s %s - received data: %s" % (priv_addr[0], priv_addr[1], data))
        pub_addr = string_to_addr(data)
        # 5. reply back to server with what we received from them
        send_msg(self.server, addr_to_string(pub_addr))

        # 7. receive peer address for the peer that the public server matched us with
        data = recv_msg(self.server)
        pubdata, privdata = data.split(b'|')
        client_pub_addr = string_to_addr(pubdata)
        client_priv_addr = string_to_addr(privdata)
        print("client public is %s and private is %s, peer public is %s private is %s" % (pub_addr, priv_addr, client_pub_addr, client_priv_addr))

        # try to both connect to the peer and accept connection from peer. whichever works faster. or works at all
        threads = {
            # '0_accept': Thread(target=accept, args=(priv_addr[1],)),
            '1_accept': Thread(target=self.accept, args=(client_pub_addr[1],)),
            '2_connect': Thread(target=self.connect, args=(priv_addr, client_pub_addr,)),
            # '3_connect': Thread(target=connect, args=(priv_addr, client_priv_addr,)),
        }
        for name in sorted(threads.keys()):
            print('start thread %s' % name)
            threads[name].start()

        # Join all threads
        while threads or not self.STOP.is_set():
            keys = list(threads.keys())
            time.sleep(0.01)
            for name in keys:
                # try:
                #     # threads[name].join(5) # wait for 5 sec for thread to finish
                #     # threads[name].join(0.1) # wait for 0.1 sec for thread to finish
                # except TimeoutError:
                #     continue
                if not threads[name].is_alive():
                    threads.pop(name)

        if self.STOP.is_set():
            print("STOP is set, connection to peer established")
            # print(self.socket)
            # self.socket.settimeout(900)
            # remove timeout
            if self.socket:
                self.socket.settimeout(None)

        print("THREADS ENDED")

    def send(self, key: str, data: bytes):
        if not self.socket:
            self._connect(key)

        self.socket.send(str(len(data)).rjust(16).encode("utf-8"))
        self.socket.send(data)

    def receive(self, key: str) -> bytes:
        if not self.socket:
            self._connect(key)

        message = b""
        data = self.socket.recv(16)

        if not data:
            return b""

        size = int(data)
        while len(message) < size:
            bytes_to_receive = min(size - len(message), BUFF_SIZE)
            data = self.socket.recv(bytes_to_receive)
            message += data

        return message

    def cleanup(self, key: str):
        self.socket.close()

    def accept(self, port):
        print("accept %s" % port)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(('', port))
        s.listen(1)
        s.settimeout(5)
        while not self.STOP.is_set():
            try:
                s.settimeout(1)
                conn, addr = s.accept()
            except socket.timeout:
                print("Accept timeout, retrying...")
                continue
            else:
                print("Accept %s connected!" % port)

                if not self.STOP.is_set():
                    self.STOP.set()
                    self.socket = conn

                # if STOP.is_set():
                #     conn.close()
                #     break

                # STOP.set()
                # global accept_socket
                # accept_socket = conn
                # print(f"Got accept on port={port}")

    def connect(self, local_addr, addr):
        print("connect from %s to %s" % (local_addr, addr))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(local_addr)
        while not self.STOP.is_set():
            try:
                s.settimeout(1)
                s.connect(addr)
                print("connect from %s to %s success!" % (local_addr, addr))
                # send_msg(s, addr_to_string(local_addr))
                if not self.STOP.is_set():
                    self.STOP.set()
                    self.socket = s
            except socket.error:
                continue
            # except Exception as exc:
            #     logger.exception("unexpected exception encountered")
            #     break
            # else:
                # print("connected from %s to %s success!" % (local_addr, addr))

                # if STOP.is_set():
                #     s.close()
                #     break

                # STOP.set()
                # global connect_socket
                # connect_socket = s
                # print(f"Got super socket in connect local_addr={local_addr} addr={addr}")

