#coding=utf-8
#!/usr/bin/env python

__author__ = 'yuanwm <ywmpsn@163.com>'

import paramiko
import os
import select
import sys
import tty
import termios

'''
在这里定义IP与用户名以及密码，暂时使用字典定义（防止无第三方的模块解析配置文件）
'''
HostMsg = {
    "103.46.128.49":{
        "account":{
            "HostPassWord": "ie5Pxi$t",
            "HostPort": "19776"
        }
    },
    "10.113.178.111": {
        "Note":"预演环境1号机",
        "account": {
            "HostPassWord": "iC4me#ck"
        }
    }
}


class SSHConnect( object ):
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
    def connect(self):
        """
        与指定主机建立Socket连接
        """
        # 建立socket
        self._Trans = paramiko.Transport((self._HostIp, int(self._Port)))

        # 启动客户端
        self._Trans.start_client()
        # 如果使用rsa密钥登录的话
        '''
        default_key_file = os.path.join(os.environ['HOME'], '.ssh', 'id_rsa')
        prikey = paramiko.RSAKey.from_private_key_file(default_key_file)
        trans.auth_publickey(username='super', key=prikey)
        '''
        # 使用用户名和密码登录
        self._Trans.auth_password(username = self._UserName, password = self._PassWord)

        # 封装transport
        self._SSH = paramiko.SSHClient()
        self._SSH._transport = self._Trans
        # 自动添加策略，保存服务器的主机名和密钥信息
        self._SSH.set_missing_host_key_policy(paramiko.AutoAddPolicy())

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
                        print("\r\n 连接已断开 \r\n")
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
        self._Trans.close()

if __name__ == "__main__":

    #执行一个终端
    if len(sys.argv) < 4:
        os.system('''echo "参数错误!,例如：
        %s -xshell 192.168.1.1 account (执行一个xshell终端)
        %s -sh 192.168.1.1 account 'df -h' (执行df -h这个命令并返回)"'''
        % (sys.argv[0],sys.argv[0]))
        exit(1)
    OperaType=sys.argv[1]
    HostIp = sys.argv[2]
    HostName = sys.argv[3]

    # 获取密码
    try:
        HostPassword = HostMsg[HostIp][HostName]['HostPassWord']
        HostPort = HostMsg[HostIp][HostName]['HostPort']
    except Exception as ErrMsg:
        print('获取主机信息错误![%s]' % ErrMsg)
        exit(0)

    ssh = SSHConnect(HostIp, HostPort, HostName, HostPassword)
    try:
        ssh.connect()
        if OperaType == '-xshell':
            ssh.x_shell()
        elif OperaType == '-sh':
            command = sys.argv[4]
            ssh.shell_cmd(command)
    except Exception as ErrMsg:
        print('执行错误![%s]' % ErrMsg)
        exit(0)

    finally:
        ssh.disconnect()
