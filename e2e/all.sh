#!/bin/bash
set -e

green=$(tput setaf 2)
reset=$(tput sgr0)

info() { echo "${green}$1${reset}"; }

benchmark() {
  local method="$1"
  local dataset="$2"
  local count="$3"
  local epochs="$4"

  info "==> Benchmarking: method=$method dataset=$dataset count=$count epochs=$epochs"
  info "=> Warmup"

  if [[ "$method" == "efs" ]]; then
    NO_VPC=""
  else
    NO_VPC="--no-vpc"
  fi

  python call.py $NO_VPC --method "$method" --count "$count"

  file=results/$method-$dataset-e$epochs-c$count.jsonl

  # Truncate file
  echo "" > $file

  # Run benchmark
  for i in `seq 10`; do
    info "=> Run $i"
    python call.py $NO_VPC --method "$method" --count "$count" >> $file
  done
}

mkdir -p results/

if [[ "$1" == "vpc" ]]; then
  benchmark efs mnist 4 5
  benchmark efs mnist 6 5
  benchmark efs mnist 10 5
fi

if [[ "$1" == "no-vpc" ]]; then
  benchmark s3 mnist 4 5
  benchmark dynamodb mnist 4 5
  benchmark redis mnist 4 5
  benchmark relay mnist 4 5
  benchmark p2p mnist 4 5

  benchmark s3 mnist 6 5
  benchmark dynamodb mnist 6 5
  benchmark redis mnist 6 5
  benchmark relay mnist 6 5
  benchmark p2p mnist 6 5

  benchmark s3 mnist 10 5
  benchmark dynamodb mnist 10 5
  benchmark redis mnist 10 5
  benchmark relay mnist 10 5
  benchmark p2p mnist 10 5
fi

