from abc import ABC, abstractmethod
from .bulletin import Communicator


class Operation(ABC):
    communicator_class: Communicator

    def __init__(self, communicator_class: Communicator):
        self.communicator_class = communicator_class

    @abstractmethod
    def execute(self, rank: int, root: int, key: str, data: bytes = b"") -> bytes:
        pass


class BroadcastOperation(Operation):
    def execute(self, rank: int, root: int, key: str, data: bytes = b"") -> bytes:
        return b""


class GatherOperation(Operation):
    def execute(self, rank: int, root: int, key: str, data: bytes = b"") -> bytes:
        return b""


# def master_broadcast(data):
#     log("master_broadcast")
#     global communicators, rank, key, count, nth_comm
#     nth_comm += 1

#     if rank == 0:
#         threads = []
#         for i in range(1, count):
#             threads.append(
#                 Thread(
#                     target=send,
#                     args=(f"{key}-{i}", f"{key}-{i}-{nth_comm}", data)
#                 )
#             )
#         start_and_join(threads)
#         return data
#     else:
#         return receive(f"{key}-0", f"{key}-{rank}-{nth_comm}")


# def master_gather(data):
#     log("master_gather")
#     global communicator, rank, key, count, nth_comm
#     nth_comm += 1

#     if rank == 0:
#         data = []
#         # for i in range(1, count):
#         #     data.append(receive(f"{key}-{i}", f"{key}-{i}-{nth_comm}"))
#         with ThreadPoolExecutor() as executor:
#             futures = [executor.submit(receive, f"{key}-{i}", f"{key}-{i}-{nth_comm}") for i in range(1, count)]
#             for future in futures:
#                 data.append(future.result())
#         return data
#     else:
#         send(f"{key}-0", f"{key}-{rank}-{nth_comm}", data)
#         return []
