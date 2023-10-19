import yaml
from .bulletin import Communicator, S3Communicator, DynamoDBCommunicator, EFSCommunicator, RedisCommunicator, RelayCommunicator, P2PCommunicator


class BulletinRule:
    vpc: "bool | None"
    fully_serverless: "bool | None"
    event_size: "dict | None"
    method: str

    def __init__(self, method: str, vpc: "bool | None" = None, fully_serverless: "bool | None" = None, event_size: "dict | None" = None):
        self.method = method
        self.vpc = vpc
        self.fully_serverless = fully_serverless
        self.event_size = event_size

    def matches(self, vpc: bool, fully_serverless: bool, event_size: int) -> bool:
        if self.vpc is not None and self.vpc != vpc:
            return False

        if self.fully_serverless is not None and self.fully_serverless != fully_serverless:
            return False

        if self.event_size is not None:
            if "less_than_or_eq" in self.event_size and event_size > self.event_size["less_than_or_eq"]:
                return False
            if "greater_than_or_eq" in self.event_size and event_size < self.event_size["greater_than_or_eq"]:
                return False
            if "less_than" in self.event_size and event_size >= self.event_size["less_than"]:
                return False
            if "greater_than" in self.event_size and event_size <= self.event_size["greater_than"]:
                return False

        return True


class BulletinConfig:
    rules: list[BulletinRule]
    config: dict

    def __init__(self, config: dict, rules: list[BulletinRule]):
        self.config = config
        self.rules = rules

    @staticmethod
    def from_file(path: str):
        with open(path, "r") as file:
            config = yaml.safe_load(file)

        rules = []
        for rule in config["rules"]:
            rules.append(BulletinRule(**rule))

        return BulletinConfig(config["config"], rules)

    def choose_method(self, vpc: bool, fully_serverless: bool, event_size: int) -> str:
        for rule in self.rules:
            if rule.matches(vpc, fully_serverless, event_size):
                return rule.method

        return Exception("No matching rule found")


class AutoCommunicator(Communicator):
    config: dict
    vpc: bool
    fully_serverless: bool
    communicators: dict[str, Communicator]
    sizes: dict[str, int]

    def __init__(self, config: BulletinConfig, vpc: bool, fully_serverless: bool):
        super().__init__()
        self.config = config
        self.vpc = vpc
        self.fully_serverless = fully_serverless
        self.communicators = {}
        self.sizes = {}

    def send(self, key: str, data: bytes):
        self._get_communicator(len(data)).send(key, data)
        self.sizes[key] = len(data)

    def receive(self, key: str, expected_size: int) -> bytes:
        self.sizes[key] = expected_size
        return self._get_communicator(expected_size).receive(key)

    def cleanup(self, key: str):
        self._get_communicator(self.sizes[key]).cleanup(key)

    def _get_communicator(self, event_size: int) -> Communicator:
        method = self.config.choose_method(
            self.vpc, self.fully_serverless, event_size)

        if method not in self.communicators:
            self.communicators[method] = self._create_communicator(method)

        return self.communicators[method]

    @property
    def usage(self) -> dict[str, int]:
        return self._get_communicator(list(self.sizes.values())[0]).usage

    def _create_communicator(self, name: str) -> Communicator:
        if name == "s3":
            return S3Communicator(self.config.config["s3"]["bucket"])
        elif name == "dynamodb":
            return DynamoDBCommunicator(self.config.config["dynamodb"]["table"])
        elif name == "efs":
            return EFSCommunicator(self.config.config["efs"]["mount_path"])
        elif name == "redis":
            return RedisCommunicator(self.config.config["redis"]["host"], self.config.config["redis"]["port"])
        elif name == "relay":
            return RelayCommunicator(self.config.config["relay"]["host"], self.config.config["relay"]["port"])
        elif name == "p2p":
            return P2PCommunicator(self.config.config["p2p"]["host"], self.config.config["p2p"]["port"])


# config = BulletinConfig.from_file("bulletin/src/bulletin/bulletin_policy.yml")

# import code; code.interact(local=dict(globals(), **locals()))
