#!/usr/bin/env python

import os, sys, shutil, pathlib
from fuse import FUSE, FuseOSError, Operations

class FilterFS(Operations):
    def __init__(self, source, cache):
        self.source = source
        self.cache = cache
    def _original(self, path):
        print(path)
        p = os.path.join(self.source, path.lstrip('/'))
        if os.path.islink(p):
            rl = os.readlink(p)
            if rl.startswith('/!/'):
                cached_output = os.path.join(self.cache, path.lstrip('/'))
                if not os.path.exists(cached_output):
                    rl = rl[3:]
                    d = os.path.dirname(p)
                    # begin hack
                    old_cwd = os.getcwd()
                    os.chdir(d)
                    os.system(rl)
                    os.chdir(old_cwd)
                    pathlib.Path(os.path.dirname(cached_output)).mkdir(parents = True, exist_ok = True)
                    shutil.move(os.path.join(d, 'out'), cached_output)
                    # end hack
                p = cached_output
        return p

    # directory
    def readdir(self, path, fh):
        yield '.'
        yield '..'
        if os.path.isdir(self._original(path)):
            for d in os.listdir(self._original(path)):
                yield d

    # directory, file etc.
    def getattr(self, path, file_handle = None):
        st = os.lstat(self._original(path))
        return {
            'st_mode': st.st_mode, # 0o100775 file, 0o40775 dir
            #'st_ino': 42,
            #'st_dev': 123,
            'st_nlink': st.st_nlink,
            'st_uid': st.st_uid,
            'st_gid': st.st_gid,
            'st_size': st.st_size,
            'st_atime': st.st_atime,
            'st_mtime': st.st_mtime,
            'st_ctime': st.st_ctime,
        }
    
    # file
    def open(self, path, flags):
        return os.open(self._original(path), flags)
    def read(self, path, length, offset, file_handle):
        os.lseek(file_handle, offset, os.SEEK_SET)
        return os.read(file_handle, length)

def main(source, cache, mountpoint):
    FUSE(FilterFS(source, cache), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])