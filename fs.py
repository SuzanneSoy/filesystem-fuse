#!/usr/bin/env python

import os, sys, errno, shutil, pathlib
from fuse import FUSE, FuseOSError, Operations
from collections import namedtuple

Translator = namedtuple('Translator', ['mode', 'output_filename', 'command'])
# todo: rename 'path' to 'get'
Entity = namedtuple('Entity', ['path', 'is_translator', 'peek', 'source', 'size'])

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

    def _get(self, why, path):
        print('get', why, path)
        p = os.path.join(self.source, path.lstrip('/'))
        if os.path.islink(p):
            rl = os.readlink(p)
            if rl.startswith('/!/'):
                cached_output = os.path.join(self.cache, 'get', path.lstrip('/'))
                peek = os.path.join(self.cache, 'peek', path.lstrip('/'))
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
                    attr = os.lstat(p)
                    os.utime(cached_output, (attr.st_ctime, attr.st_mtime))
                    os.utime(peek, (attr.st_ctime, attr.st_mtime))
                p = cached_output
        return p
    
    def _get_source(self, why, path):
        print("_get_source", why, path)
        return os.path.join(self.source, path.lstrip('/'))
    
    def _get_entity(self, why, path):
        print("_get_entity", why, path)
        p = os.path.join(self.source, path.lstrip('/'))
        if os.path.islink(p):
            rl = os.readlink(p)
            if rl.startswith('/!/'):
                get = os.path.join(self.cache, 'get', path.lstrip('/'))
                peek = os.path.join(self.cache, 'peek', path.lstrip('/'))
                if os.path.exists(get):
                    return Entity(path = get, is_translator = True, peek = peek, source = p, size = None)
                else:
                    translator = self._parse(rl)
                    self._mkparents(peek)
                    pathlib.Path(peek).touch()
                    attr = os.lstat(p)
                    os.utime(peek, (attr.st_ctime, attr.st_mtime))
                    os.chmod(peek, translator.mode)
                    return Entity(path = peek, is_translator = True, peek = peek, source = p, size = 0)
        return Entity(path = p, is_translator = False, peek = p, source = p, size = None)

    # directory
    def readdir(self, path, fh):
        yield '.'
        yield '..'
        orig = self._get("readdir", path)
        if os.path.isdir(orig):
            for d in os.listdir(orig):
                yield d
    def mkdir(self, path, mode):
        pass
    def rmdir(self, path):
        pass

    # directory, file etc
    def getattr(self, path, file_handle = None):
        entity = self._get_entity("getattr", path)
        attr = os.lstat(entity.path)
        print(entity.path)
        return {
            'st_mode': attr.st_mode, # 0o100775 file, 0o40775 dir
            #'st_ino': 42,
            #'st_dev': 123,
            'st_nlink': attr.st_nlink,
            'st_uid': attr.st_uid,
            'st_gid': attr.st_gid,
            'st_size': attr.st_size if entity.size is None else entity.size,
            'st_atime': attr.st_atime,
            'st_mtime': attr.st_mtime,
            'st_ctime': attr.st_ctime,
        }

    def access(self, path, mode):
        entity = self._get_entity("access", path)
        if not os.access(entity.path, mode):
            raise FuseOSError(errno.EACCES)
    
    def chmod(self, path, mode):
        return os.chmod(self._get_entity('chmod', path).peek, mode)
    def chown(self, path, uid, gid):
        return os.chown(self._get_source('chown', path), uid, gid)
    def rename(self, old_path, new_path):
        old_entity = self._get_entity('rename old', old_path)
        new_entity = self._get_entity('rename new', new_path)
        if os.path.exists(new_entity.source):
            raise FuseOSError(errno.EACCES)
        else:
            if entity.is_translator:
                # TODO: preserve the cache for moved file?
                os.unlink(old_entity.path)
                os.unlink(old_entity.peek)
                return os.rename(old_entity.source, new_entity.source)
            else:
                return os.unlink(entity.path, mode)
    def utimens(self, path, times=None):
        # TODO: the "peek" should have an utime in addition to a chmod
        return os.utime(self._get_entity('utimens', path).peek, times)
    def unlink(self, path):
        entity = self._get_entity('unlink', path)
        if entity.is_translator:
            os.unlink(entity.path)
            os.unlink(entity.peek)
            return os.unlink(entity.source)
        else:
            return os.unlink(entity.path, mode)
    def link(self, original_path, clone_path):
        print('link', original_path, clone_path, 'TODO')
        pass

    # other:
    def mknod(self, path, mode, dev):
        return os.mknod(self._get_entity('mknod', path).source, mode, dev)

    # filesystem
    def statfs(self, path):
        pass
    
    # symlinks
    def readlink(self, path):
        pass
    def symlink(self, destination, symlink_path):
        pass
    
    # file
    def open(self, path, flags):
        print('open', path, flags)
        return os.open(self._get("open", path), flags)
    def read(self, path, length, offset, file_handle):
        print('read', path, length, offset, file_handle)
        self._get("read", path)
        os.lseek(file_handle, offset, os.SEEK_SET)
        r = os.read(file_handle, length)
        return r
    def _assert_is_writable(self, why, path):
        # TODO: might be a bit slow for many repeated writes, but guarantees that
        # if a translator is created in src and a file handle was already obtained
        # for its output, no further writes can mix things up?
        # TODO: write a test for the above test case
        entity = self._get_entity("_assert_is_writable for " + why, path)
        if entity.is_translator:
            raise FuseOSError(errno.EACCES)
        else:
            return entity
    def write(self, path, buffer, offset, file_handle):
        self._assert_is_writable("write", path)
        os.lseek(file_handle, offset, os.SEEK_SET)
        return os.write(file_handle, buffer)
    def create(self, path, mode, file = None):
        entity = self._assert_is_writable("write", path)
        return os.open(entity.path, os.O_CREAT | os.O_WRONLY, mode)
    def truncate(self, path, length, file_handle = None):
        entity = self._assert_is_writable("truncate", path)
        with open(entity.path, 'r+') as f:
            f.truncate(length)
    def flush(self, path, file_handle):
        #self._assert_is_writable("flush", path)
        return os.fsync(file_handle)
    def release(self, path, file_handle):
        print('release', path)
        return os.close(file_handle)
    def fsync(self, path, fdatasync, file_handle):
        self._assert_is_writable("fsync",path)
        return self.flush(path, file_handle)

def main(source, cache, mountpoint):
    # direct_io allows us to return size 0 for non-empty files
    FUSE(FilterFS(source, cache), mountpoint, nothreads=True, foreground=True, direct_io = True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])

# TODO: an option to check that commands are signed with a trusted GPG key before executing them
#       This would allow the user to run this on a filesystem containing a mix of trusted and
#       untrusted files (e.g. tar -zxf untrusted-downloaded-file.tar.gz is dangerous). In order to
#       prevent replay attacks, the signed data should include things like the path to the
#       symlink-command (otherwise re-using that signed symlink-command in another location with
#       different files could be used to change the semantics of the command), and/or the inputs
#       (the command itself and the hash of the input files)