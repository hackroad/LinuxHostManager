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
import stat
import logging
import subprocess
import datetime
import time
import struct
import fcntl


# like invoke() of fabric
def pty_size():
    """
    Determine current local pseudoterminal dimensions.

    :returns:
        A ``(num_cols, num_rows)`` two-tuple describing PTY size. Defaults to
        ``(80, 24)`` if unable to get a sensible result dynamically.

    .. versionadded:: 1.0
    """
    cols = os.get_terminal_size().columns
    rows = os.get_terminal_size().lines
    print(cols,rows)
    #if not WINDOWS else _win_pty_size()
    # TODO: make defaults configurable?
    return ((cols or 80), (rows or 24))

class SSHConnection(object):
    """定义一个类SSH客户端对象
    """
    def __init__(self, host_ip, port, user_name, pass_word, key_file=None, timeout=None):
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
        self._KeyFile = key_file
        self._TimeOut = timeout
        # 日志定义
        self._Log = logging
        self._Log.basicConfig( level=logging.ERROR,
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
        self._Trans.start_client(timeout=self._TimeOut)

        if self._KeyFile is not None:   # 如果使用rsa密钥登录, password 可能指定也可能不
            pri_key = paramiko.RSAKey.from_private_key_file(filename=self._KeyFile, password=self._PassWord)
            self._Trans.auth_publickey(username=self._UserName, key=pri_key)
        else:
            # 使用用户名和密码登录
            self._Trans.auth_password(username=self._UserName, password=self._PassWord)
        # 封装transport，一个高级的socket client，主要用于shell命令的执行
        self._SSH = paramiko.SSHClient()
        self._SSH._transport = self._Trans

        # 自动添加策略，保存服务器的主机名和密钥信息
        self._SSH.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        return True

    def sftp_get(self, remote_path, local_path, callback_object=None):
        """
        实现SFTP功能下载文件功能
        :param remote_path: 远端目录、文件路径，必须是绝对的
        :param local_path: 必须是文件
        :param callback_object: 回调函数参数，一般是留个多进程使用
        :return:成功: 无异常  失败: 异常
        """
        # 传入为空检测
        if len(remote_path) == 0 or len(local_path) == 0:
            raise ValueError("路径存在空的情况![{}][{}]".format(remote_path, local_path))
        # 本地路径路径绝对化
        local_path = os.path.abspath(local_path)
        # 定义连接
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        '''
        由于不支持本地路径，需要指定文件；因此，如果传入的是本地路径，则默认传到该路径下，文件名为原文件名
        '''
        # 解析文件列表，主要是通配符的检测
        remote_path_list = self.remote_path_parse(remote_path)

        # 如果有通配符，这个列表会有多个文件，反正遍历一次
        for tmp_remote_path in remote_path_list:
            # 检测远端文件合法性，并分离路径与文件名
            remote_file_stat = self._Sftp.stat(tmp_remote_path)
            if stat.S_ISDIR(remote_file_stat.st_mode):
                raise TypeError('远端[{}]是目录'.format(tmp_remote_path))
            (remote_file_path, remote_file_name) = os.path.split(tmp_remote_path)

            # 本地文件名组合
            try:
                local_path_stat = os.stat(local_path)
                if stat.S_ISDIR(local_path_stat.st_mode):
                    local_file_path = local_path + os.path.sep + remote_file_name
                else:
                    local_file_path = local_path
            except IOError:  # 如果没有这个目录/文件夹，默认以此为文件
                local_file_path = local_path
            # 文件下载文件
            self._Log.info('下载:get[{}]from[{}]'.format(local_file_path, tmp_remote_path))
            # 定义一些临时的sftp类变量，用于回调函数使用
            self._Sftp.cur_file = remote_file_name
            self._Sftp.begin_time = datetime.datetime.now()
            self._Sftp.up_time = None
            self._Sftp.up_cur_size = None
            self._Sftp.up_speed_rate = None
            self._Sftp.task_que_file_size = None
            if callback_object is not None:
                self._Sftp.task_que_file_size = callback_object
            # 进行远端的md5值进行判断，如果相同则不需要再传
            try:
                self.comp_local_remote_md5(local_file_path, tmp_remote_path)
                self.view_bar(remote_file_stat.st_size, remote_file_stat.st_size) #直接显示百分之百
            except Exception:   # 有异常则需要进行重新传输
                self._Sftp.get(tmp_remote_path, local_file_path, callback=self.view_bar)
                self.comp_local_remote_md5(local_file_path, tmp_remote_path)
                # 由于文件大小为0是不会触发stp回调函数，因此，这里需要显示的调用
                if remote_file_stat.st_size == 0:
                    self.view_bar(0, 0)

    def sftp_put(self, local_path_list_in, remote_path, callback_object=None):
        """
        实现SFTP功能上传文件功能
        :param local_path_in: 本地必须是文件
        :param remote_path: 远端目录、文件路径，必须是绝对的
        :param callback_object: 回调函数参数，一般是留个多进程使用
        :return:成功: 无异常  失败: 异常
        """
        if len(remote_path) == 0 or len(local_path_list_in) == 0:
            raise ValueError("路径存在空的情况![{}][{}]".format(remote_path, local_path_list_in))

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

        # 本地文件路径绝对化
        local_path_list = []
        for tmp_path in local_path_list_in:
            local_path_list.append(os.path.abspath(tmp_path))
        # 解析文件列表---本地不需要解析
        # local_path_list = self.local_path_parse(local_path_list_in)

        for tmp_local_path in local_path_list:
            (local_file_path, local_file_name) = os.path.split(tmp_local_path)
            local_path_stat = os.stat(tmp_local_path)
            if stat.S_ISDIR(local_path_stat.st_mode):
                raise TypeError('不能上传目录![{}]'.format(tmp_local_path))
            # 路径作特殊处理
            try:
                remote_path_stat = self._Sftp.stat(remote_path)
                if stat.S_ISDIR(remote_path_stat.st_mode):
                    remote_file_path = remote_path + os.path.sep + local_file_name
                else:
                    remote_file_path = remote_path
            except IOError:  # 如果没有这个目录/文件夹，默认以此为文件
                remote_file_path = remote_path
            self._Log.info('上传文件:put[{}]to[{}]'.format(tmp_local_path, remote_file_path))
            # 定义一些临时的sftp类变量，用于回调函数使用
            self._Sftp.cur_file = local_file_name
            self._Sftp.begin_time = datetime.datetime.now()
            self._Sftp.up_time = None
            self._Sftp.up_cur_size = None
            self._Sftp.up_speed_rate = None
            self._Sftp.task_que_file_size = None
            if callback_object is not None:
                self._Sftp.task_que_file_size = callback_object

            # 进行远端的md5值进行判断，如果相同则不需要再传
            try:
                self.comp_local_remote_md5(tmp_local_path, remote_file_path)
                self.view_bar(local_path_stat.st_size, local_path_stat.st_size) #直接显示百分之百
            except Exception as err_msg:   # 有异常则需要进行重新传输
                self._Sftp.put(tmp_local_path, remote_file_path, callback=self.view_bar)
                self.comp_local_remote_md5(tmp_local_path, remote_file_path)
                # 由于文件大小为0是不会触发stp回调函数，因此，这里需要显示的调用
                if local_path_stat.st_size == 0:
                    self.view_bar(0, 0)

    @staticmethod
    def delete_object_sep(dec_object):
        """
        去掉目录最后的sep分割,windows为'\',Linux为'/'，此处无windows
        :param dec_object: 目标对象
        :return: 去掉sep的对象
        """
        if len(dec_object) == 0 | len(dec_object) == 1:     # 如果为1则有可能是根目录，也没必要进行去分隔符
            return dec_object
        if dec_object[-1] == '\\' or dec_object[-1] == '/':
            dec_object = dec_object[0:-1]
        return dec_object

    def judge_local_path_stat(self, local_path_in):
        """
        判断本地路径存在与否，存在返回属性
        :param local_path_in: 本地路径
        :return:成功: 对象状态  失败: 异常
        """
        if len(local_path_in) == 0:
            raise ValueError("路径存在空的情况![{}]".format(local_path_in))

        # 取绝对路径+去掉分隔符
        local_path = os.path.abspath(local_path_in)
        local_path = self.delete_object_sep(local_path)

        # 路径作特殊处理
        local_path_stat = os.stat(local_path)
        self._Log.info('目标状态[{}]'.format(local_path_stat.st_mode))
        return local_path_stat.st_mode

    def judge_remote_path_stat(self, remote_path_in):
        """
        判断远程路径存在与否，存在返回属性
        :param remote_path_in: 远程路径
        :return: 成功: 对象状态  失败: 异常
        """
        if len(remote_path_in) == 0:
            raise ValueError("路径存在空的情况![{}]".format(remote_path_in))

        if self._Sftp is None:
            self._Log.info('建立SFTP连接')
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)

        # 去掉分隔符
        remote_path = self.delete_object_sep(remote_path_in)
        # 路径作特殊处理
        remote_path_stat = self._Sftp.stat(remote_path)
        self._Log.info('目标状态[{}]'.format(remote_path_stat))
        return remote_path_stat.st_mode

    def local_path_parse(self, local_path_in):
        """
        解析列表中含有通配符的路径，最后再进行去重即可（防止已经包含通配符解析内容）
        本地使用解析通配符
        :param local_path_in: 输入本地路径
        :return:失败:异常  成功:路径列表
        """
        # 清理'/'符号
        local_path = self.delete_object_sep(local_path_in)

        # 取绝对路径，并进行分离
        local_abs_path = os.path.abspath(local_path)
        (local_top_path, local_match_str) = os.path.split(local_abs_path)

        local_path_list = []  # 初始化一个文件路径列表
        # 如果匹配字符串不为0，且含有?或者*才识别为通配符
        if len(local_match_str) != 0 & (local_match_str.find('?') is True or local_match_str.find('*') is True):
            local_path_stat = os.stat(local_top_path)
            if stat.S_ISDIR(local_path_stat.st_mode):
                local_file_list = os.listdir(local_top_path)
                for tmp_file_name in local_file_list:
                    # 目标名不匹配则删除
                    if self.match_wildcard(tmp_file_name, local_match_str) is True:
                        local_path_list.append(local_top_path + os.sep + tmp_file_name)
            else:
                raise TypeError('上级路径不为目录[{}]'.format(local_top_path))
        # 如果为0就不正常
        elif len(local_match_str) != 0:
            tmp_file_path = local_top_path + os.sep + local_match_str
            local_path_list.append(tmp_file_path)
        else:
            raise ValueError('文件路径[{}]识别错误!'.format(local_path_in))

        self._Log.info('识别的文件列表:[{}]'.format(local_path_list))

        # 文件列表为空也报错
        if len(local_path_list) == 0:
            raise ValueError('文件路径[{}]未找到识别的文件列表!'.format(local_path_in))

        return local_path_list

    def remote_path_parse(self, remote_path_in):
        """
        解析通配符
        :param remote_path_in:远端路径
        :return:失败:异常 成功:路径列表
        """
        # 清理'/'符号
        local_path = self.delete_object_sep(remote_path_in)

        # 不能为绝对路径
        (remote_top_path, remote_match_str) = os.path.split(remote_path_in)

        if self._Sftp is None:
            self._Log.info('建立SFTP连接')
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)

        remote_path_list = []  # 初始化一个文件路径列表
        # 如果匹配字符串不为0，且含有?或者*才识别为通配符
        if len(remote_match_str) != 0 & (remote_match_str.find('?') is True or remote_match_str.find('*') is True):
            remote_path_stat = self._Sftp.stat(remote_top_path)
            if stat.S_ISDIR(remote_path_stat.st_mode):
                remote_file_list = self._Sftp.listdir(remote_top_path)
                for tmp_file_name in remote_file_list:
                    # 目标名不匹配则删除
                    if self.match_wildcard(tmp_file_name, remote_match_str) is True:
                        remote_path_list.append(remote_top_path + os.sep + tmp_file_name)
            else:
                raise TypeError('上级路径[{}]不为目录！'.format(remote_top_path))
        # 如果不为0就不正常
        elif len(remote_match_str) != 0:
            tmp_file_path = remote_top_path + os.sep + remote_match_str
            remote_path_list.append(tmp_file_path)
        else:
            raise ValueError('文件路径[{}]识别错误!'.format(remote_path_in))

        self._Log.info('识别的文件列表:[{}]'.format(remote_path_list))

        # 文件列表为空也报错
        if len(remote_path_list) == 0:
            raise ValueError('文件路径[{}]未找到识别的文件列表!'.format(remote_path_in))

        return remote_path_list

    def shell_cmd(self, cmd):
        """
        在主机上执行单个shell命令
        :param cmd: 执行的shell命令
        :return state 执行shell的结果状态
        """
        if len(cmd) == 0:
            raise ValueError('命令为空，请重新输入!')
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
            rows, cols = pty_size()
            self._XShellChan.get_pty(width=rows, height=cols)
            # 激活终端，这样就可以登录到终端了，就和我们用类似于XShell登录系统一样
            self._XShellChan.invoke_shell()
            # 获取原操作终端属性
        old_tty_arg = termios.tcgetattr(sys.stdin)
        try:
            # 将现在的操作终端属性设置为服务器上的原生终端属性,可以支持tab了
            tty.setraw(sys.stdin)
            tty.setcbreak(sys.stdin)
            self._XShellChan.settimeout(0)
            while True:
                read_list, write_list, err_list = select.select([self._XShellChan, sys.stdin, ], [], [])
                # 如果是用户输入命令了,sys.stdin发生变化
                if sys.stdin in read_list:
                	# 循环读取发送
                    # 获取输入的内容，输入一个字符发送1个字符
                    input_cmd = sys.stdin.read(1)
                    # 将命令发送给服务器
                    self._XShellChan.sendall(input_cmd.encode('utf-8'))

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
                    #sys.stdout.write(result.decode()) #modify by yandong :python2就是打印的bytes,不需要转换
                    sys.stdout.write(result.decode('utf-8'))
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

    @staticmethod
    def match_wildcard(s, p):
        """
        字符串匹配，power by workflow
        :param s: 目标字符串
        :param p:为含有通配符的字符串
        :return: 成功:True  失败：False
        """
        dp = [[False for i in range(len(p) + 1)] for j in range(len(s) + 1)]
        dp[0][0] = True

        for i in range(1, len(p) + 1):
            if p[i - 1] == '*':
                dp[0][i] = dp[0][i - 1]

        for i in range(1, len(s) + 1):
            for j in range(1, len(p) + 1):
                if p[j - 1] == '*':
                    dp[i][j] = dp[i][j - 1] or dp[i - 1][j - 1] or dp[i - 1][j]
                else:
                    dp[i][j] = (s[i - 1] == p[j - 1] or p[j - 1] == '?') and dp[i - 1][j - 1]
        return dp[len(s)][len(p)]

    def remote_md5_get(self, remote_path_in):
        """远程文件的md5值获取，利用远程shell-md5sum执行即可，python本身的md5获取较慢
        remote_path_in：传入必须是绝对路径
        retrun 失败:异常 成功:md5值
        """
        stdin, stdout, stderr = self._SSH.exec_command('md5sum {}'.format(remote_path_in))

        # 返回状态获取
        chan = stdout.channel
        status = chan.recv_exit_status()
        if status != 0:     # 次命令Linux中返回值不为0则为错误
            err_msg = stderr.read().decode()
            raise OSError('获取[{}]md5错误![{}]'.format(remote_path_in, err_msg))
        else:
            out_msg = str(stdout.read().decode()).split(' ')
            self._Log.info('获取[{}]md5成功![{}]'.format(remote_path_in, out_msg[0]))
            return out_msg[0]

    def local_md5_get(self, local_path_in):
        """本地文件的md5值获取，利用远程shell-md5sum执行即可，python本身的md5获取较慢
        remote_path_in：传入必须是绝对路径
        retrun 失败:异常 成功:md5值
        """

        shell_cmd = ('md5sum {}'.format(local_path_in))
        ShellPopen = subprocess.Popen(shell_cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        ShellPopen.wait()
        output = ShellPopen.stdout.read().decode()
        errput = ShellPopen.stderr.read().decode()
        status = ShellPopen.returncode

        if status != 0:     # 次命令Linux中返回值不为0则为错误
            raise OSError('获取[{}]md5错误![{}]'.format(local_path_in, errput))
        else:
            out_msg = str(output).split(' ')
            self._Log.info('获取[{}]md5成功![{}]'.format(local_path_in, out_msg[0]))
            return out_msg[0]

    def comp_local_remote_md5(self, local_path_in, remote_path_in):
        """
        本地文件与远端文件md5值比较
        :param local_path_in:
        :param remote_path_in:
        :return: 成功：True  失败：异常
        """
        # 获取本地文件md5值
        local_file_md5 = self.local_md5_get(local_path_in)

        # 获取本地文件md5值
        remote_file_md5 = self.remote_md5_get(remote_path_in)

        # 远程文件md5值并进行比较
        if local_file_md5 != remote_file_md5:
            raise ValueError('本地文件[{}]与远端文件[{}]对应md5[{}][{}]不一致!'.format(local_path_in, remote_path_in,
                                                                         local_file_md5, remote_file_md5))
        return True
    def view_bar(self, cur_file_size, total_file_size):
        """
        进度显示,暂定样式:
        源文件名    [======]    100%    35kb/36kb    35KB/s  00:00:00(预计剩余时间)   00:00:00(花费总时间)
        这里计算过多，会造成传输的延迟。
        :param cur_file_size:当前文件大小
        :param total_file_size:文件总大小
        :param src_file_name
        :return:
        """
        # 对于多进程进行特殊处理
        if self._Sftp.task_que_file_size is not None:
            # 这里只能返回增量大小，因为多进程是累加进行统计。
            if self._Sftp.up_cur_size is None:
                self._Sftp.task_que_file_size.put(cur_file_size)
            else:
                self._Sftp.task_que_file_size.put(cur_file_size - self._Sftp.up_cur_size)
            self._Sftp.up_cur_size = cur_file_size  # 多进程单个文件显示一次
            if cur_file_size != total_file_size:    # 多进程处理文件，必须要等文件处理完才显示进度
                return

            # 进度条比例（***这里可以自定义修改*******）
        sum_process = 10
        # 速率统计间隔时间，秒级别
        speed_space_time = 1

        # 初始数据获取
        src_file_name = self._Sftp.cur_file
        task_begin_time_in = self._Sftp.begin_time

        # 获取上一次的时间
        if self._Sftp.up_time is None:
            self._Sftp.up_time = task_begin_time_in
        task_up_time_in = self._Sftp.up_time

        # 获取上一次的大小
        if self._Sftp.up_cur_size is None or self._Sftp.task_que_file_size is not None: #多进程的情况
            up_file_size = 0
        else:
            up_file_size = self._Sftp.up_cur_size

        # 回调的时候时间
        task_cur_time_in = datetime.datetime.now()

        # 比例
        if total_file_size == 0:    # 空文件
            rate = 1
        else:
            rate = cur_file_size / total_file_size
        # 总体百分比
        rate_percent = int(rate * 100)
        # 进度条
        rate_num = int(rate * sum_process)
        # 总体花费时间
        task_begin_time = task_begin_time_in.strftime('%Y-%m-%d %H:%M:%S')
        task_cur_time = task_cur_time_in.strftime('%Y-%m-%d %H:%M:%S')
        spend_time = datetime.datetime.strptime(task_cur_time, '%Y-%m-%d %H:%M:%S') - \
                     datetime.datetime.strptime(task_begin_time, '%Y-%m-%d %H:%M:%S')

        # 当前传输速率，记录上一次的大小、以及上一次的时间
        # 由于调用一次可能时间间隔过短，看不出效果，因此，速率这个地方设置为speed_space_time间隔时间才进行统计，
        # 否则取上一次的速率，第一次除外。
        task_up_time = task_up_time_in.strftime('%Y-%m-%d %H:%M:%S')
        cur_spend_time = datetime.datetime.strptime(task_cur_time, '%Y-%m-%d %H:%M:%S') - \
                     datetime.datetime.strptime(task_up_time, '%Y-%m-%d %H:%M:%S')
        cur_spend_time_seconds = cur_spend_time.seconds

        # 第一次计算或者符合计算条件。或者已经传输完毕
        if self._Sftp.up_speed_rate is None or cur_spend_time_seconds >= speed_space_time:
            if cur_spend_time_seconds == 0:     # 分母不能为0
                cur_spend_time_seconds = 1
            speed_rate = int((cur_file_size - up_file_size) / cur_spend_time_seconds)

            # 记录此次的有用数据
            self._Sftp.up_cur_size = cur_file_size
            self._Sftp.up_time = task_cur_time_in
            self._Sftp.up_speed_rate = speed_rate
            # 防止妨碍显示
            #self._Log.info('当前间隔时间{},当前传输大小{},上次传输大小{}'.format(cur_spend_time_seconds,
                                                                        # cur_file_size, up_file_size))
        else:   # 小于统计间隔时间，不用计算，此次不做任何记录
            # 取上一次的速率即可
            speed_rate = self._Sftp.up_speed_rate

        # 计算后的展示
        show_speed_rate = self.converting_bytes(speed_rate)

        # 计算预计剩余时间
        if speed_rate == 0:
            pre_spend_time_second = 0
        else:
            pre_spend_time_second = int((total_file_size-cur_file_size) / speed_rate)   # 秒
        ori_old_time_arry = time.localtime(0)     # 最原始时间:一般1970
        pre_spend_time_arry = time.localtime(pre_spend_time_second)

        # 进行转换计算
        ori_old_time = time.strftime("%Y-%m-%d %H:%M:%S", ori_old_time_arry)
        pre_spend_time_tmp = time.strftime("%Y-%m-%d %H:%M:%S", pre_spend_time_arry)
        pre_spend_time = datetime.datetime.strptime(pre_spend_time_tmp, '%Y-%m-%d %H:%M:%S') - \
                     datetime.datetime.strptime(ori_old_time, '%Y-%m-%d %H:%M:%S')

        # 大小转换为b/kb/M/GB
        show_total_file_size = self.converting_bytes(total_file_size)
        show_cur_file_size = self.converting_bytes(cur_file_size)
        show_file_speed = "{}/{}".format(show_cur_file_size, show_total_file_size)

        try:
            file_name_len = os.get_terminal_size().columns-110
        except OSError:
            file_name_len = 40
        if len(src_file_name)<file_name_len:
            file_name_show = "{}{}".format(src_file_name, (file_name_len-len(src_file_name)) * " ")
        else:
            file_name_show = "{}% ".format(src_file_name)
        show_percent='{}%'.format(rate_percent)
        r = '\r%-40s%-6s%22s%15s/s%10s%10s' % (file_name_show, show_percent, show_file_speed,
                                                show_speed_rate, pre_spend_time, spend_time)
        # 多进程的明细文件，只有百分之百才打印输出，并且要覆盖整个一行，防止与多进程统计输出重复
        if self._Sftp.task_que_file_size is not None and rate == 1 and total_file_size == cur_file_size:
            sys.stdout.write('{}                                                            '.format(r))
            sys.stdout.flush()
        elif rate == 1 and total_file_size == cur_file_size:   # 已经百分之百
            sys.stdout.write('{}\n'.format(r))
            sys.stdout.flush()
        else:
            sys.stdout.write(r)
            sys.stdout.flush()

        return

    @staticmethod
    def converting_bytes(Byte):
        """
         by stackoverflow.com
        Return the given bytes as a human friendly KB, MB, GB, or TB string
        :Byte B: Input is Byte
        :return:
        """
        B = float(Byte)
        KB = float(1024)
        MB = float(KB ** 2)  # 1,048,576
        GB = float(KB ** 3)  # 1,073,741,824
        TB = float(KB ** 4)  # 1,099,511,627,776

        if B < KB:
            return '{0} {1}'.format(B, 'Bytes' if 0 == B > 1 else 'Byte')
        elif KB <= B < MB:
            return '{0:.2f} KB'.format(B / KB)
        elif MB <= B < GB:
            return '{0:.2f} MB'.format(B / MB)
        elif GB <= B < TB:
            return '{0:.2f} GB'.format(B / GB)
        elif TB <= B:
            return '{0:.2f} TB'.format(B / TB)

