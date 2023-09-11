#!/usr/bin/env bash

set -euET -o pipefail

rm test -fr
mkdir test test/cache test/mnt
cp -ai source test/source
./fs.py test/source test/cache test/mnt & pid=$!

run_tests() {
  touch test/mnt/touched
  echo 42 > test/mnt/written
  cp -ai test/mnt test/actual_result
  diff -r test/actual_result expected_test_result
}

if run_tests; then
  echo success
  kill -KILL $pid
  fusermount -u test_mnt
else
  echo failed
  kill -KILL $pid
  fusermount -u test_mnt
fi