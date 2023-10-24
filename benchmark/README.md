## Setup

```bash
aws ec2 import-key-pair --key-name <name> --public-key-material file:///Users/<name>/.ssh/id_ed25519.pub

export AWS_PROFILE=voc
./apply
./benchmark.py s3
```

```bash
./benchmark.py -s1 -n10 relay | jq -s 'map(.total_time) | add/length'
```

