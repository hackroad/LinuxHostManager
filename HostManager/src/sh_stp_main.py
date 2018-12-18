# coding=utf-8
# !/usr/bin/env python

__author__ = 'yuanwm <ywmpsn@163.com>'

import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from paramiko_sh import SSHConnection
from multistp import MultiSftp
import sys


def load_host_msg():
    """
    加载主机信息
    """
    host_msg_file_path = "/Users/yuanwm/Code/actsrc/app/LinuxHostManager/HostManager/cfg/host_cfg.json"
    try:
        with open("{}".format(host_msg_file_path), 'r') as load_msg:
            host_cfg_msg = json.load(load_msg)
    except Exception as err_msg:
        raise ('主机信息文件[{}]读取错误[{}]\n'.format(host_msg_file_path, err_msg))
    return host_cfg_msg


def get_host_msg(host_name_ip):
    """
    根据用户名与ip获取主机的密码与端口信息
    :param host_name_ip: 如:account@192.168.1.7
    :return:
    """
    # 获取密码
    HostMsg = load_host_msg()
    if host_name_ip not in HostMsg:
        raise ValueError('无主机[{}]信息!'.format(host_name_ip))
    if "HostPassWord" not in HostMsg[HostNameIp]:
        raise ValueError('无主机[{}]密码配置信息!'.format(host_name_ip))
    host_password = HostMsg[host_name_ip]["HostPassWord"]
    if "HostPort" not in HostMsg[host_name_ip]:
        raise ValueError('无主机[{}]端口配置信息!'.format(host_name_ip))
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
python %s -putdir 本地文件/目录 account@192.168.1.1:远程文件/目录(上传文件/目录到远程主机) (进程数，默认10)
python %s -getdir account@192.168.1.1:远程文件/目录 本地文件/目录(下载文件/目录到本地主机) (进程数，默认10)
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
        elif OperaType == '-sh':  # 执行远程shell命令
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
            ret = ssh.shell_cmd(command)
            ssh.disconnect()
            exit(ret)
        elif OperaType == '-put':  # 上传文件
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -put 本地文件 account@192.168.1.1:远程文件/目录(上传文件到远程主机)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)
            RemoteMsg = sys.argv[len(sys.argv) - 1]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
            ssh.connect()
            remote_path = RemoteMsg.split(':')[1]
            # 本地路径应该解析为列表
            local_path_list = []
            # 从第二个到倒数第二个都应该为目标参数
            for i in range(2, len(sys.argv) - 1, 1):
                local_path_list.append(sys.argv[i])

            ssh.sftp_put(local_path_list, remote_path)

            ssh.disconnect()
        elif OperaType == '-get':  # 下载文件
            if len(sys.argv) < 4:
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
        elif OperaType == '-getdir':  # 下载目录
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -getdir account@192.168.1.1:远程文件/目录 本地文件/目录(下载文件/目录到本地主机) (进程数，默认10)
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
            # max_process_num = 0
            # if len(sys.argv) > 4:
            #     max_process_num = int(sys.argv[4])
            # else:
            #     max_process_num = 5
            multi_sftp = MultiSftp(HostIp, HostPort, HostName, HostPassword)
            multi_sftp.sftp_get_dir(remote_path, local_path)

        elif OperaType == '-putdir':  # 上传目录
            if len(sys.argv) < 4:
                sys.stderr.write('''参数错误!,例如：
                python %s -putdir 本地文件/目录 account@192.168.1.1:远程文件/目录(上传文件/目录到远程主机) (进程数，默认10)
                ''' % sys.argv[0])
                sys.stderr.flush()
                exit(1)

            # 这里主机信息是最后一个字段
            RemoteMsg = sys.argv[len(sys.argv) - 1]
            HostNameIp = RemoteMsg.split(':')[0]
            HostName = HostNameIp.split('@')[0]
            HostIp = HostNameIp.split('@')[1]
            (HostPassword, HostPort) = get_host_msg(HostNameIp)
            remote_path = RemoteMsg.split(':')[1]

            # 本地路径应该解析为列表
            local_path_list = []
            # 从第二个到倒数第二个都应该为目标参数
            for i in range(2, len(sys.argv) - 1, 1):
                local_path_list.append(sys.argv[i])
            # 最大进程数定义
            # max_process_num = 0
            # if le# n(sys.argv) > 4:
            #     max_process_num = int(sys.argv[4])
            # else:
            #     max_process_num = 5
            multi_sftp = MultiSftp(HostIp, HostPort, HostName, HostPassword)
            multi_sftp.sftp_put_dir(local_path_list, remote_path)
        else:
            sys.stderr.write("不支持操作类型[%s]\n" % OperaType)
            sys.stderr.flush()
            exit(1)
    except KeyboardInterrupt:   # 按键中断直接退出
        sys.stderr.write("\n*WOW*按键中断**\n")
        sys.stderr.flush()
        exit(1)
    except Exception as err_msg:
        sys.stderr.write('操作[{}]执行错误![{}]\n'.format(OperaType, err_msg))
        sys.stderr.flush()
        exit(1)
