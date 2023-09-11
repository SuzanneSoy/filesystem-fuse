#!/usr/bin/env bash

set -euET -o pipefail

rm test_cache test_source test_actual_result -fr
mkdir -p test_cache test_mnt
cp -ai source test_source
./fs.py test_source test_cache test_mnt
touch test_mnt/touched
echo 42 > test_mnt/written
cp -ai test_mnt test_actual_result
diff -r test_actual_result test_expected_result