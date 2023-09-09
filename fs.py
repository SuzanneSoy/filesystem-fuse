#!/usr/bin/env python

import os, sys, shutil, pathlib
from fuse import FUSE, FuseOSError, Operations
from collections import namedtuple

Translator = namedtuple('Translator', ['mode', 'output_filename', 'command'])

class FilterFS(Operations):
    def __init__(self, source, cache):
        self.source = source
        self.cache = cache
    
    def _mkparents(self, f):
        pathlib.Path(os.path.dirname(f)).mkdir(parents = True, exist_ok = True)
    def _parse(self, s):
        if not s.startswith('/!/'):
            return None
        s = s[3:]
        components = s.split('/')
        return Translator(
            mode = int(components[0], base=8),
            output_filename = components[1], # TODO: forbid ../ attacks
            command = '/'.join(components[2:])
        )
    def _peek(self, why, path):
        print('peek', path)
        p = os.path.join(self.source, path.lstrip('/'))
        if os.path.islink(p):
            rl = os.readlink(p)
            if rl.startswith('/!/'):
                get = os.path.join(self.cache, 'get', path.lstrip('/'))
                peek = os.path.join(self.cache, 'peek', path.lstrip('/'))
                if os.path.exists(get):
                    p = get
                else:
                    translator = self._parse(rl)
                    p = peek
                    self._mkparents(p)
                    pathlib.Path(p).touch()
                    os.chmod(p, translator.mode)
        return p

    def _get(self, why, path):
        print('get', why, path)
        p = os.path.join(self.source, path.lstrip('/'))
        if os.path.islink(p):
            rl = os.readlink(p)
            if rl.startswith('/!/'):
                cached_output = os.path.join(self.cache, 'get', path.lstrip('/'))
                if not os.path.exists(cached_output):
                    translator = self._parse(rl)
                    d = os.path.dirname(p)
                    # begin hack
                    old_cwd = os.getcwd()
                    os.chdir(d)
                    os.system(translator.command)
                    os.chdir(old_cwd)
                    self._mkparents(cached_output)
                    shutil.move(os.path.join(d, translator.output_filename), cached_output)
                    # end hack
                p = cached_output
        return p

    # directory
    def readdir(self, path, fh):
        yield '.'
        yield '..'
        orig = self._get("readdir", path)
        if os.path.isdir(orig):
            for d in os.listdir(orig):
                yield d

    # directory, file etc.
    def getattr(self, path, file_handle = None):
        st = os.lstat(self._peek("getattr", path))
        return {
            'st_mode': st.st_mode, # 0o100775 file, 0o40775 dir
            #'st_ino': 42,
            #'st_dev': 123,
            'st_nlink': st.st_nlink,
            'st_uid': st.st_uid,
            'st_gid': st.st_gid,
            'st_size': 999999999999999, #st.st_size, # TODO: max file size
            'st_atime': st.st_atime,
            'st_mtime': st.st_mtime,
            'st_ctime': st.st_ctime,
        }
    
    # file
    def open(self, path, flags):
        return os.open(self._get("open", path), flags)
    def read(self, path, length, offset, file_handle):
        os.lseek(file_handle, offset, os.SEEK_SET)
        return os.read(file_handle, length)

def main(source, cache, mountpoint):
    FUSE(FilterFS(source, cache), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])