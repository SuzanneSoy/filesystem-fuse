#!/usr/bin/env bash

set -euET -o pipefail

fusermount -u test/mnt || true
rm test -fr
mkdir test test/cache test/mnt
cp -ai source test/source

find test/source -print0 | xargs -0r touch --no-dereference --date="2023-01-01 00:00Z"
find expected_test_result -print0 | xargs -0r touch --no-dereference --date="2023-01-01 00:00Z"

# TODO: are the chmod preserved by git commit + git checkout ?

./fs.py test/source test/cache test/mnt > test/fs.log & pid=$!

run_tests() {
  # make sure any mtime errors will show up
  sleep 1.1

  # TODO: use foreground=False instead of & pid=$!
  for i in `seq 20`; do
    if test -e test/mnt/exists; then
      break
    else
        printf '.'
        sleep 0.1
    fi
  done
  printf '\n'

  echo 01; test -e test/mnt/exists
  echo 02; touch --date='2023-02-02 00:00Z' test/mnt/touch  && touch --date='2023-02-02 00:00Z'        expected_test_result/touch
  echo 03; touch --date='2023-02-02 00:00Z' test/mnt/create && touch --date='2023-02-02 00:00Z'        expected_test_result/create
  echo 04; echo 42 > test/mnt/create_write                  && touch --reference=test/mnt/create_write expected_test_result/create_write
  echo 05; echo 'Append' >> test/mnt/append                 && touch --reference=test/mnt/append       expected_test_result/append
  echo 06; echo 'This is an overwrite' > test/mnt/overwrite && touch --reference=test/mnt/overwrite    expected_test_result/overwrite
  echo 07; truncate --size=6 test/mnt/truncate              && touch --reference=test/mnt/truncate     expected_test_result/truncate
  echo 08; mknod -m 644 test/mnt/mknod644p p                && touch --reference=test/mnt/truncate     expected_test_result/mknod644p
  # TODO: test that a _peek cached but not _get cached file has the correct mtime?
  
  # reset the mtime of the modified directories
  #touch --date='2023-01-01 00:00Z' test/mnt/some_dir # unmodified
  touch --date='2023-01-01 00:00Z' test/mnt

  echo 99; cp -ai test/mnt test/actual_result
  echo uu; fusermount -u test/mnt
  echo ta; tar -cf test/actual.tar   -C test/actual_result/   .
  echo te; tar -cf test/expected.tar -C expected_test_result/ .
  echo dd; diffoscope test/actual.tar test/expected.tar
}

if run_tests; then
  printf '\033[1;32mSuccess\033[m\n'
else
  printf '\033[1;31mFailure\033[m\n'
  fusermount -u test/mnt || kill -KILL $pid
  exit 1
fi

# TODO: tests for ctime
#       e.g. using https://serverfault.com/questions/520322/unix-ctime-how-to-keep-this-precious-information-in-backups-tar
#       or https://www.halfgaar.net/backing-up-unix
#       or simply find -print0 | xargs -0 stat
#       Note that on ext4 we can't access this information without root permissions: https://unix.stackexchange.com/questions/50177/birth-is-empty-on-ext4