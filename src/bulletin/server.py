import socket
import threading
import traceback
import logging
from abc import ABC, abstractmethod

from .p2p_utils import string_to_addr, addr_to_string, send_msg, recv_msg, P2PClient

MEGABYTE = 1000*1000
BUFF_SIZE = 1*MEGABYTE

class Server(ABC):
    address: str
    port: int

    def __init__(self, address="0.0.0.0", port=12345):
        self.address = address
        self.port = port

    @abstractmethod
    def run(self):
        pass


class RelayServer(Server):
    channels: dict[str, list[socket.socket]]
    message_history: dict[str, list[str]]

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.address, self.port))
        server.listen(5)

        # Clients grouped by channel
        self.channels = {}
        # Message history for each channel
        self.message_history = {}

        print(f"[*] Server started on {self.address}:{self.port}. Waiting for connections...")
        while True:
            client_socket, client_address = server.accept()
            client_thread = threading.Thread(
                target=self.handle_client,
                args=(client_socket, client_address))
            client_thread.start()

    def handle_client(self, client_socket, client_address):
        print(f"[+] {self.client_name(client_address)} connected.")

        channel = ""

        while True:
            try:
                message = self.socket_receive_message(client_socket)
                if message:
                    try:
                        msg = self._parse_message(message)
                    except Exception as e:
                        print(f"[E] decode error for", message)
                        raise e

                    action = msg['action']

                    if action == 'subscribe':
                        channel = msg['channel']
                        if channel not in self.channels:
                            self.channels[channel] = []
                        self.channels[channel].append(client_socket)
                        print(f"[J] {self.client_name(client_address)} joined channel '{channel}'")
                        self.send_history(channel, client_socket, self.message_history)

                    elif action == 'publish':
                        channel = msg['channel']
                        message = self._build_message(msg['action'], msg['channel'], msg['message'])
                        print(f"[P] {self.client_name(client_address)} -> {channel}")
                        if channel in self.channels:
                            self.relay_message(channel, client_socket, message, self.channels)
                        else:
                            if channel not in self.message_history:
                                self.message_history[channel] = []
                            self.message_history[channel].append(message)

                else:
                    break
            except Exception as e:
                print("[E] Error:", e)
                traceback.print_exc()
                break

    def client_name(self, client_address):
        return f"{client_address[0]}:{client_address[1]}"

    def socket_send_message(self, socket, data):
        socket.send(str(len(data)).ljust(16).encode("utf-8"))
        socket.send(data)

    def socket_receive_message(self, s):
        message = b""
        data = s.recv(16)

        if not data:
            return b""

        size = int(data)
        while len(message) < size:
            bytes_to_receive = min(size - len(message), BUFF_SIZE)
            data = s.recv(bytes_to_receive)
            message += data

        return message

    def relay_message(self, channel, sender_socket, message, channels):
        for client in channels[channel]:
            if client != sender_socket:
                self.socket_send_message(client, message)

    def send_history(self, channel, client_socket, message_history):
        if channel in message_history:
            for message in message_history[channel]:
                self.socket_send_message(client_socket, message)

            del message_history[channel]

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

# Inspired by https://github.com/dwoz/python-nat-hole-punching/blob/master/util.py
class P2PServer(Server):
    clients: dict[str, socket.socket]

    def __init__(self, address="0.0.0.0", port=12345):
        super().__init__(address, port)
        self.clients = {}
        self.list = {}

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.address, self.port))
        s.listen(1)
        s.settimeout(30)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        logger = logging.getLogger()

        logger.info('server - listening on %s:%s', self.address, self.port)

        while True:
            try:
                conn, addr = s.accept()
            except socket.timeout:
                continue

            logger.info('connection address: %s', addr)
            data = recv_msg(conn)
            addr_str, key = data.split(b'|')
            priv_addr = string_to_addr(addr_str)
            send_msg(conn, addr_to_string(addr))
            data = recv_msg(conn)
            data_addr = string_to_addr(data)

            if data_addr != addr:
                logger.info('client reply did not match')
                conn.close()
                continue

            logger.info('client reply matches')
            logger.info('server - received data: %s', data)

            if key not in self.list:
                self.list[key] = P2PClient(conn, addr, priv_addr)
            else:
                c1, c2 = self.list[key], P2PClient(conn, addr, priv_addr)
                logger.info('server - send client info to: %s', c1.pub)
                send_msg(c1.conn, c2.peer_msg())
                logger.info('server - send client info to: %s', c2.pub)
                send_msg(c2.conn, c1.peer_msg())
                self.list.pop(key)
