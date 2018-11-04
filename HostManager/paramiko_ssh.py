# coding=utf-8
# !/usr/bin/env python

# -*- encoding: utf-8 -*-

__author__ = 'yuanwm <ywmpsn@163.com>'

import paramiko
import select
import sys
import tty
import termios
import os
from stat import S_ISDIR
import logging


class SSHConnection(object):
    """定义一个类SSH客户端对象
    """
    def __init__(self, host_ip, port, user_name, pass_word):
        """
        初始化各类属性
        """
        self._HostIp = host_ip
        self._Port = int(port)
        self._UserName = user_name
        self._PassWord = pass_word
        self._Trans = None
        self._XShellChan = None
        self._SSH = None
        self._Sftp = None
        # 日志定义
        self._Log = logging
        self._Log.basicConfig(level=logging.DEBUG,
                                      format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                                      datefmt='%a, %d %b %Y %H:%M:%S'
                                        )

    def connect(self):
        """
        与指定主机建立Socket连接
        """
        # 建立socket
        self._Trans = paramiko.Transport(self._HostIp, self._Port)

        # 启动客户端
        self._Trans.start_client()
        # 如果使用rsa密钥登录的话--这里一般不用直接注释了
        '''
        key_file = '~.ssh/id_rsa'
        pri_key = paramiko.RSAKey.from_private_key_file(default_key_file)
        self._Trans.auth_publickey(username = self._UserName, key=prikey)
        '''
        # 使用用户名和密码登录
        self._Trans.auth_password(username=self._UserName, password=self._PassWord)

        # 封装transport
        self._SSH = paramiko.SSHClient()
        self._SSH._transport = self._Trans

        # 自动添加策略，保存服务器的主机名和密钥信息
        self._SSH.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        return True

    def sftp_get(self, remote_path, local_path):
        """
        实现SFTP功能下载文件功能
        :param remote_path: 远端目录、文件路径，必须是绝对的
        :param local_path:必须是文件
        :return:成功: True  失败: False
        """
        # 传入为空检测
        if len(remote_path) == 0 or len(local_path) == 0:
            self._Log.error("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False

        # 本地路径路径绝对化
        local_path = os.path.abspath(local_path)

        # 定义连接
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        '''
        由于不支持本地路径，需要指定文件；因此，如果传入的是本地路径，则默认传到该路径下，文件名为原文件名
        '''

        # 检测远端文件合法性，并分离路径与文件名
        remote_file_stat = self._Sftp.stat(remote_path)
        if S_ISDIR(remote_file_stat.st_mode):
            self._Log.error('远端[%s]是目录' % remote_path)
            return False
        (remote_file_path, remote_file_name) = os.path.split(remote_path)

        # 本地文件名组合
        try:
            local_path_stat = os.stat(local_path)
            if S_ISDIR(local_path_stat.st_mode):
                local_file_path = local_path+os.path.sep+remote_file_name
            else:
                local_file_path = local_path
        except IOError:      # 如果没有这个目录/文件夹，默认以此为文件
            local_file_path = local_path

        # 下载文件
        self._Log.info('下载:get[%s]from[%s]' % (local_file_path, remote_path))
        try:
            self._Sftp.get(remote_path, local_file_path)
        except Exception as err_msg:
            self._Log.error('获取文件失败![%s]' % err_msg)
            return False
        return True

    def sftp_put(self, local_path, remote_path):
        """
        实现SFTP功能上传文件功能
        :param local_path: 本地必须是文件
        :param remote_path: 远端目录、文件路径，必须是绝对的
        :return:成功: True  失败: False
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            self._Log.error("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False

        if self._Sftp is None:
            self._Log.info('建立SFTP连接')
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        '''
        由于不支持远程路径，需要指定文件；因此，如果传入的是远程路径，则默认传到该路径下，文件名为原文件名
        '''
        # 去掉分隔符
        if remote_path[-1] == os.path.sep:
            remote_path = remote_path[0:-1]
        # 路径作特殊处理
        try:
            remote_path_stat = self._Sftp.stat(remote_path)
            if S_ISDIR(remote_path_stat.st_mode):
                (local_file_path, local_file_name) = os.path.split(local_path)
                remote_file_path = remote_path+os.path.sep+local_file_name
            else:
                remote_file_path = remote_path
        except IOError:      # 如果没有这个目录/文件夹，默认以此为文件
            remote_file_path = remote_path
        try:
            self._Sftp.put(local_path, remote_file_path)
        except Exception as err_msg:
            self._Log.error('上传文件失败![%s]' % err_msg)
            return False
        return True

    def shell_cmd(self, cmd):
        """
        在主机上执行单个shell命令
        """
        if len(cmd) == 0:
            self._Log.error('命令为空，请重新输入!')
            return False

        stdin, stdout, stderr = self._SSH.exec_command(cmd)
        chan = stdout.channel

        # 返回状态获取
        status = chan.recv_exit_status()

        # 分别返回标准错误，标准输出
        out = stdout.read()
        if len(out) > 0:
            out.strip()
            sys.stdout.write(out.decode())
            sys.stdout.flush()
        err = stderr.read()
        if len(err) > 0:
            err.strip()
            sys.stderr.write(err.decode())
            sys.stderr.flush()

        # 返回shell命令的状态
        return status

    def x_shell(self):
        """
        实现一个XShell，登录到系统就不断输入命令同时返回结果,支持自动补全，直接调用服务器终端
        """
        # 打开一个通道
        if self._XShellChan is None:
            self._XShellChan = self._Trans.open_session()
            # 获取终端
            self._XShellChan.get_pty()
            # 激活终端，这样就可以登录到终端了，就和我们用类似于XShell登录系统一样
            self._XShellChan.invoke_shell()
            # 获取原操作终端属性
        old_tty_arg = termios.tcgetattr(sys.stdin)
        try:
            # 将现在的操作终端属性设置为服务器上的原生终端属性,可以支持tab了
            tty.setraw(sys.stdin)
            self._XShellChan.settimeout(0)
            while True:
                read_list, write_list, err_list = select.select([self._XShellChan, sys.stdin, ], [], [])
                # 如果是用户输入命令了,sys.stdin发生变化
                if sys.stdin in read_list:
                    # 获取输入的内容，输入一个字符发送1个字符
                    input_cmd = sys.stdin.read(1)
                    # 将命令发送给服务器
                    self._XShellChan.sendall(input_cmd)

                # 服务器返回了结果,self._XShellChan通道接受到结果,发生变化 select感知到
                if self._XShellChan in read_list:
                    # 获取结果
                    result = self._XShellChan.recv(65535)
                    # 断开连接后退出
                    if len(result) == 0:
                        sys.stdout.write("\t**连接已断开，欢迎再回来**\n")
                        sys.stdout.flush()
                        break
                    # 输出到屏幕
                    sys.stdout.write(result.decode())
                    sys.stdout.flush()
        finally:
            # 执行完后将现在的终端属性恢复为原操作终端属性
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_arg)
        return True

    def disconnect(self):
        """
        主机任务结束后执行
        """
        # 关闭链接
        if self._Trans is not None:
            self._Trans.close()
        if self._XShellChan is not None:
            self._XShellChan.close()
        if self._Sftp is not None:
            self._Sftp.close()
        if self._SSH is not None:
            self._SSH.close()
        return True

