import time
import socket
import json
import threading
import os

SERVER_IP = "44.204.170.154"
MEGABYTE = 1000*1000
BUFF_SIZE = MEGABYTE

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, 12345))

message_size = 150_000_000

message = "a" * message_size

payload = json.dumps({
    "action": "publish",
    "channel": "test",
    "message": message,
}).encode("utf-8")

client.send(f"{len(payload)}".encode("utf-8"))
client.recv(1024)
client.send(payload)

print("Sent message:", len(payload))
