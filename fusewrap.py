#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
'''Easy mounting fuse fs, with autocomplete'''

import argcomplete
import argparse
from pathlib import Path
from os.path import expanduser
from subprocess import Popen
from typing import List
import sys
import os


HOME_PATH = Path(expanduser('~'))
DEFAULT_SSH_CFG_PATH = HOME_PATH / '.ssh/config'
DEFAULT_MOUNT_PATH = HOME_PATH / 'mnt'


class FuseMount:
    def __init__(self, path: Path):
        self.path = path


class SSHostname:
    def __init__(self, name: str):
        self._name = name

    def get_path(self, root: Path) -> Path:
        return root / self._name

    def get_mount_root(self):
        return f'{self._name}:/'

    def is_mounted(self, root: Path, fuses: List[FuseMount]) -> bool:
        path = self.get_path(root)
        for fuse in fuses:
            if path == fuse.path:
                return True
        return False

    def __eq__(self, obj: object) -> bool:
        if isinstance(obj, SSHostname):
            return obj._name == self._name
        raise TypeError(f"Wants {self.__class__.__name__}")

    def __str__(self) -> str:
        return self._name


class FuseWrapException(Exception):
    pass


class FuseWrap:
    def __init__(self, args):
        self._mount_path = Path(expanduser(args.mount_dir_path))
        self._ssh_cfg_path = DEFAULT_SSH_CFG_PATH
        self._fuse_mounts = self._get_fuse_mounts()
        self._hosts = self._get_hostnames(self._ssh_cfg_path)

    @staticmethod
    def _get_fuse_mounts() -> List[FuseMount]:
        result: List[FuseMount] = []
        with open('/proc/mounts', 'r') as f:
            for line in f.readlines():
                tokens = line.split()
                if tokens[2] == 'fuse.sshfs':
                    result.append(FuseMount(Path(tokens[1])))
        return result

    @staticmethod
    def _get_hostnames(path) -> List[SSHostname]:
        result = []
        with open(path, 'r') as ssh_cfg:
            while (line := ssh_cfg.readline()):
                if line.startswith('Host'):
                    result.append(SSHostname(line.split()[1]))
        return result

    def _check_host(self, hostname: SSHostname):
        if hostname not in self._hosts:
            raise FuseWrapException(f"There is no {hostname} hostname in {self._ssh_cfg_path}")

    @property
    def mount_path(self):
        return self._mount_path

    def get_mounted(self):
        return [hostname for hostname in self._hosts
                if hostname.is_mounted(self._mount_path, self._fuse_mounts)]

    def get_unmounted(self):
        return [hostname for hostname in self._hosts
                if not hostname.is_mounted(self._mount_path, self._fuse_mounts)]

    def mount(self, host: SSHostname):
        self._check_host(host)
        mount_point = host.get_path(self._mount_path)
        if host in self.get_mounted():
            raise FuseWrapException(f"Host {host} already mounted in {mount_point}")
        os.makedirs(mount_point, exist_ok=True)
        args = ['sshfs', host.get_mount_root(), str(mount_point)]
        print('"{}"'.format(' '.join(args)))
        job = Popen(args)
        job.communicate()

    def umount(self, host: SSHostname):
        self._check_host(host)
        mount_point = host.get_path(self._mount_path)
        if host in self.get_unmounted():
            raise FuseWrapException(f"Host {host} already unmounted")
        args = ['fusermount', '-u', str(mount_point)]
        print('"{}"'.format(' '.join(args)))
        job = Popen(args)
        job.communicate()
        os.rmdir(mount_point)


def job_list(args):
    fuse_wrap = FuseWrap(args)
    for mnt in fuse_wrap.get_mounted():
        print(f'{mnt} -> {fuse_wrap.mount_path}/{mnt}')
    if args.all:
        for mnt in fuse_wrap.get_unmounted():
            print(f'{mnt} -> empty')


def job_mount(args):
    fuse_wrap = FuseWrap(args)
    fuse_wrap.mount(SSHostname(args.hostname))


def job_umount(args):
    fuse_wrap = FuseWrap(args)
    fuse_wrap.umount(SSHostname(args.hostname))


def complete_mounted(prefix, parsed_args, **kwargs):
    fuse_wrap = FuseWrap(parsed_args)
    return [str(host_name) for host_name in fuse_wrap.get_mounted()]


def complete_unmounted(prefix, parsed_args, **kwargs):
    fuse_wrap = FuseWrap(parsed_args)
    return [str(host_name) for host_name in fuse_wrap.get_unmounted()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mount-dir-path',
                        default=DEFAULT_MOUNT_PATH,
                        help=f"Directory for mounts, default: {DEFAULT_MOUNT_PATH}")
    commands = parser.add_subparsers()

    cmd_list_hosts = commands.add_parser('list', help='list of mounted sshfs')
    cmd_list_hosts.add_argument('-a', '--all', action='store_true', help='list unmounted too')
    cmd_list_hosts.set_defaults(job=job_list)

    cmd_mount_hosts = commands.add_parser('mount', help='mount form ssh config file')
    cmd_mount_hosts.add_argument('hostname', help="hostname in ssh cfg").completer = complete_unmounted
    cmd_mount_hosts.set_defaults(job=job_mount)

    cmd_unmount_hosts = commands.add_parser('umount', help='umount form ssh config file')
    cmd_unmount_hosts.add_argument('hostname', help="hostname in ssh cfg").completer = complete_mounted
    cmd_unmount_hosts.set_defaults(job=job_umount)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    if not hasattr(args, 'job'):
        parser.print_help()
        exit(1)
    try:
        return args.job(args)
    except FuseWrapException as err:
        print(f'ERR: {err}', file=sys.stderr)
    except KeyboardInterrupt:
        print('Job canceled')


if __name__ == '__main__':
    exit(main())
