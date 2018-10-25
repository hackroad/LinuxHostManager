#coding=utf-8
#!/usr/bin/env python

# -*- encoding: utf-8 -*-

__author__ = 'yuanwm <ywmpsn@163.com>'

import paramiko
import os
import select
import sys
import tty
import termios
from stat import S_ISDIR

class SSHConnection( object ):
    """定义一个类SSH客户端对象
    """

    def __init__(self, hostip, port, user_name, pass_word):
        """
        初始化各类属性
        """
        self._HostIp = hostip
        self._Port = port
        self._UserName = user_name
        self._PassWord = pass_word
        self._Trans = None
        self._XShellChan = None
        self._SSH = None
        self._Sftp = None

    def connect(self):
        """
        与指定主机建立Socket连接
        """
        # 建立socket
        self._Trans = paramiko.Transport((self._HostIp, int(self._Port)))

        # 启动客户端
        self._Trans.start_client()
        # 如果使用rsa密钥登录的话--这里一般不用直接注释了
        '''
        key_file = '~.ssh/id_rsa'
        pri_key = paramiko.RSAKey.from_private_key_file(default_key_file)
        self._Trans.auth_publickey(username = self._UserName, key=prikey)
        '''
        # 使用用户名和密码登录
        self._Trans.auth_password(username = self._UserName, password = self._PassWord)

        # 封装transport
        self._SSH = paramiko.SSHClient()
        self._SSH._transport = self._Trans
        # 自动添加策略，保存服务器的主机名和密钥信息
        self._SSH.set_missing_host_key_policy(paramiko.AutoAddPolicy())


    def get_remote_file(self, remote_dir):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        """
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        # 保存所有文件的列表
        all_files = list()
        # 只获取文件夹
        '''
        (file_path, tmp_file_name) = os.path.split(remote_dir)
        if len(tmp_file_name) != 0: #这是一个文件直接返回文件名
            all_files.append(tmp_file_name)
        else:
            file_path = file_path + '/'
        '''
        # 去掉路径字符串最后的字符'/'，如果有的话
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]
        print ('遍历目录[%s]' % remote_dir)
        # 获取当前指定目录下的所有目录及文件，包含属性值
        files = self._Sftp.listdir_attr(remote_dir)
        for x in files:
            # file_path目录中每一个文件或目录的完整路径
            file_path_name = remote_dir + '/' + x.filename
            # 如果是目录，则递归处理该目录，这里用到了stat库中的S_ISDIR方法，与linux中的宏的名字完全一致
            if S_ISDIR(x.st_mode):
                print('需要遍历目录[%s]' % file_path_name)
                all_files.extend(self.get_remote_dir_all_files(file_path_name))

            else:
                print('得到文件[%s]' % file_path_name)
                all_files.append(file_path_name)
        return all_files




    def get_remote_dir_all_files(self, remote_dir):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        """
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        # 保存所有文件的列表
        all_files = list()
        # 只获取文件夹
        '''
        (file_path, tmp_file_name) = os.path.split(remote_dir)
        if len(tmp_file_name) != 0: #这是一个文件直接返回文件名
            all_files.append(tmp_file_name)
        else:
            file_path = file_path + '/'
        '''
        # 去掉路径字符串最后的字符'/'，如果有的话
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]
        print ('遍历目录[%s]' % remote_dir)
        # 获取当前指定目录下的所有目录及文件，包含属性值
        files = self._Sftp.listdir_attr(remote_dir)
        for x in files:
            # file_path目录中每一个文件或目录的完整路径
            file_path_name = remote_dir + '/' + x.filename
            # 如果是目录，则递归处理该目录，这里用到了stat库中的S_ISDIR方法，与linux中的宏的名字完全一致
            if S_ISDIR(x.st_mode):
                print('需要遍历目录[%s]' % file_path_name)
                all_files.extend(self.get_remote_dir_all_files(file_path_name))
            else:
                print('得到文件[%s]' % file_path_name)
                all_files.append(file_path_name)
        return all_files

    def sftp_mul_thread_get_dir(self, remote_path, local_path, thread_num=0):
        """
        多线程实现SFTP功能下载文件夹功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print ("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        #判断远程目录是否存在
        tmp_cmd='(if [ ! -d "%s" ]; then  exit 1; fi)' % remote_path
        if self.shell_cmd(tmp_cmd) != 0:
            print('远程目录[%s]不存在!' % remote_path)
            return False
        # 获取远端linux主机上指定目录及其子目录下的所有文件
        all_files = self.get_remote_dir_all_files(remote_path)
        # 依次get每一个文件
        print('所有文件:')
        print(all_files)
        for x in all_files:
            filename = x.split('/')[-1]
            local_filename = os.path.join(local_path, filename)
            print("Get[%s]文件传输中..." % local_filename)
            print(x)
            self._Sftp.get(x, local_filename)
        #获取远程指定目录下的所有目录


        #多线程建立目录


        #目录建立完毕后，获取远端的所有文件信息，加入队列


        #多线程传输文件

        #try:
            #获取远程目录下的文件
         #   self._Sftp.get(remote_path, local_path)
        #except Exception as err_msg:
         #   print('获取文件失败![%s]' % err_msg)

    def sftp_get(self, remote_path, local_path):
        """
        实现SFTP功能下载文件功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print ("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        try:
            self._Sftp.get(remote_path, local_path)
        except Exception as err_msg:
            print('获取文件失败![%s]' % err_msg)

    def sftp_put(self, local_path, remote_path):
        """
        实现SFTP上传文件功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print ("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        try:
            self._Sftp.put(local_path, remote_path)
        except Exception as err_msg:
            print('上传文件失败![%s]' % err_msg)


    def shell_cmd(self, cmd):
        """
        在主机上执行单个shell命令
        """
        if len(cmd) == 0:
            os.system('echo "命令为空，请重新输入!" >&2 ')

        stdin, stdout, stderr = self._SSH.exec_command(cmd)
        chan=stdout.channel
        # 返回状态
        status=chan.recv_exit_status()

        #分别返回标准错误，标准输出
        out=stdout.read()
        if len(out) > 0:
            out.strip()
            os.system('echo "%s" >&1' % out)
        err=stderr.read()
        if len(err)>0:
            err.strip()
            os.system('echo "%s" >&2' % err)
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
                        print("\n**连接已断开**\n")
                        break
                    # 输出到屏幕
                    sys.stdout.write(result.decode())
                    sys.stdout.flush()
        finally:
            # 执行完后将现在的终端属性恢复为原操作终端属性
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_arg)
            # 关闭通道
            self._XShellChan.close()


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