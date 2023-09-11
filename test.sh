#!/usr/bin/env bash

set -euET -o pipefail

fusermount -u test/mnt || true
rm test -fr
mkdir test test/cache test/mnt
cp -ai source test/source
./fs.py test/source test/cache test/mnt & pid=$!

run_tests() {
  sleep 2 # TODO: use foreground=False instead of & pid=$!
  touch test/mnt/touched
  echo 42 > test/mnt/written
  echo 'Append' >> test/mnt/append
  echo 'This is an overwrite' > test/mnt/overwrite
  cp -ai test/mnt test/actual_result
  fusermount -u test/mnt
  diff -r test/actual_result expected_test_result
}

if run_tests; then
  printf '\033[1;32mSuccess\033[m\n'
else
  printf '\033[1;31mFailure\033[m\n'
  fusermount -u test/mnt || kill -KILL $pid
  exit 1
fi