#!/bin/bash
set -e

green=$(tput setaf 2)
reset=$(tput sgr0)

info() { echo "${green}$1${reset}"; }

benchmark() {
  local name="$1"
  local size="$2"
  local count="${3:-100}"

  info "==> Benchmarking $name with $size bytes and $count iterations"
  ./benchmark.py "$name" -s "$size" -n "$count" > "results/$name-$size-$count.jsonl"
}

mkdir -p results

# warmup
./benchmark.py s3 -s 1 -n 1

benchmark s3 1
benchmark s3 1000
benchmark s3 10000
benchmark s3 100000
benchmark s3 1000000
benchmark s3 10000000
benchmark s3 100000000

# warmup
./benchmark.py dynamodb -s 1 -n 1

benchmark dynamodb 1
benchmark dynamodb 1000
benchmark dynamodb 10000
benchmark dynamodb 100000

# warmup
./benchmark.py efs -s 1 -n 1

benchmark efs 1
benchmark efs 1000
benchmark efs 10000
benchmark efs 100000
benchmark efs 1000000
benchmark efs 10000000
benchmark efs 100000000

# warmup
./benchmark.py redis -s 1 -n 1

benchmark redis 1
benchmark redis 1000
benchmark redis 10000
benchmark redis 100000
benchmark redis 1000000
benchmark redis 10000000
benchmark redis 100000000

# warmup
./benchmark.py relay -s 1 -n 1

benchmark relay 1
benchmark relay 1000
benchmark relay 10000
benchmark relay 100000
benchmark relay 1000000
benchmark relay 10000000
benchmark relay 100000000

# warmup
./benchmark.py p2p -s 1 -n 1

benchmark p2p 1
benchmark p2p 1000
benchmark p2p 10000
benchmark p2p 100000
benchmark p2p 1000000
benchmark p2p 10000000
benchmark p2p 100000000
