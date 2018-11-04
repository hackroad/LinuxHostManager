# coding=utf-8
# !/usr/bin/env python

__author__ = 'yuanwm <ywmpsn@163.com>'

from paramiko_ssh import SSHConnection
from multisftp import MultiSftp
import sys


'''
在这里定义IP与用户名以及密码，暂时使用字典定义（防止无第三方的模块解析配置文件）
'''
HostMsg = {
    "account@103.46.128.49": {
        "HostPassWord": "ie5Pxi$t",
        "HostPort": "19776"
    },
    "account@192.168.1.7": {
        "HostPassWord": "ie5Pxi$t",
        "HostPort": "22"
    },
    "account@10.113.178.111": {
        "Note": "预演环境1号机",
        "HostPassWord": "iC4me#ck",
        "HostPort": "22"
    }
}


def get_host_msg(host_name_ip):
    """
    根据用户名与ip获取主机的密码与端口信息
    :param host_name_ip: 如:account@192.168.1.7
    :return:
    """
    # 获取密码
    if host_name_ip not in HostMsg:
        raise Exception('无主机[%s]信息!' % host_name_ip)
    if "HostPassWord" not in HostMsg[HostNameIp]:
        raise Exception('无主机[%s]密码配置信息!' % host_name_ip)
    host_password = HostMsg[host_name_ip]["HostPassWord"]
    if "HostPort" not in HostMsg[host_name_ip]:
        raise Exception('无主机[%s]端口配置信息!' % host_name_ip)
    host_port = HostMsg[host_name_ip]["HostPort"]

    return host_password, host_port


if __name__ == "__main__":
    '''
    选择方式执行对应的操作
    '''
    # 传入参数判断，至少有两个参数：argv【1】 操作，argv[2]
    if len(sys.argv) < 3:
        sys.stderr.write('''执行方式错误!,例如：
python %s -xsh account@192.168.1.1 (执行一个远程xshell终端)
python %s -sh account@192.168.1.1 'df -h' (执行远程shell命令并返回结果)
python %s -put 本地文件 account@192.168.1.1:远程文件/目录(上传文件到远程主机)
python %s -get account@192.168.1.1:远程文件 本地文件/目录(从远程主机下载文件)
python %s -putdir 本地文件/目录 account@192.168.1.1:远程文件/目录(上传文件/目录到远程主机)
python %s -getdir account@192.168.1.1:远程文件/目录 本地文件/目录(下载文件/目录到本地主机)
''' % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0]))
        sys.stderr.flush()
        exit(1)

    # ip参数解析
    OperaType = sys.argv[1]
    try:
        if OperaType == '-xsh':  # xshell窗口
            HostNameIp = sys.argv[2]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
            ssh.connect()
            ssh.x_shell()
            ssh.disconnect()
        elif OperaType == '-sh':    # 执行远程shell命令
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -sh account@192.168.1.1 'df -h' (执行远程shell命令并返回结果)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            HostNameIp = sys.argv[2]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            command = sys.argv[3]
            ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
            ssh.connect()
            ssh.shell_cmd(command)
            ssh.disconnect()
        elif OperaType == '-put':   # 上传文件
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -put 本地文件 account@192.168.1.1:远程文件/目录(上传文件到远程主机)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            RemoteMsg = sys.argv[3]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
            ssh.connect()
            remote_path = RemoteMsg.split(':')[1]
            local_path = sys.argv[2]
            ssh.sftp_put(local_path, remote_path)
            ssh.disconnect()
        elif OperaType == '-get':   # 下载文件
            if len(sys.argv) < 5:
                sys.stderr.write('''参数错误!,例如：
                python %s -get account@192.168.1.1:远程文件 本地文件/目录(从远程主机下载文件)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            RemoteMsg = sys.argv[2]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
            ssh.connect()
            remote_path = RemoteMsg.split(':')[1]
            local_path = sys.argv[3]
            ssh.sftp_get(remote_path, local_path)
            ssh.disconnect()
        elif OperaType == '-getdir':    # 下载目录
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -getdir account@192.168.1.1:远程文件/目录 本地文件/目录(下载文件/目录到本地主机)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            RemoteMsg = sys.argv[2]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            remote_path = RemoteMsg.split(':')[1]
            local_path = sys.argv[3]
            # 最大进程数定义
            max_process_num = 0
            if len(sys.argv) > 4:
                max_process_num = int(sys.argv[4])
            else:
                max_process_num = 10
            multi_sftp = MultiSftp(HostIp, HostPort, HostName, HostPassword)
            multi_sftp.sftp_get_dir(local_path, remote_path, max_process_num)
        elif OperaType == '-putdir':    # 上传目录
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -putdir 本地文件/目录 account@192.168.1.1:远程文件/目录(上传文件/目录到远程主机)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            RemoteMsg = sys.argv[3]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            remote_path = RemoteMsg.split(':')[1]
            local_path = sys.argv[2]
            # 最大进程数定义
            max_process_num = 0
            if len(sys.argv) > 4:
                max_process_num = int(sys.argv[4])
            else:
                max_process_num = 10
            multi_sftp = MultiSftp(HostIp, HostPort, HostName, HostPassword)
            multi_sftp.sftp_put_dir(local_path, remote_path, max_process_num)
        else:
            sys.stderr.write("不支持操作类型[%s]\n" % OperaType)
            sys.stderr.flush()
            exit(1)
    except Exception as ErrMsg:
        sys.stderr.write('操作[%s]执行错误![%s]\n' % (ErrMsg, OperaType))
        sys.stderr.flush()
        exit(1)


