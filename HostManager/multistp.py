# coding=utf-8
# !/usr/bin/env python

__author__ = 'yuanwm <ywmpsn@163.com>'

from stat import S_ISDIR
import os
import time
import multiprocessing
import sys
if sys.version > '3':
    import queue
    my_queue=queue
else:
    import Queue
    my_queue=Queue
    if sys.getdefaultencoding() != 'utf-8':
        reload(sys)
        sys.setdefaultencoding('utf-8')
import paramiko_sh
import logging
import paramiko


class MultiSftp(object):
    def __init__(self, host_ip, port, user_name, pass_word):
        """
        初始化各类属性
        """
        self._HostIp = host_ip
        self._Port = port
        self._UserName = user_name
        self._PassWord = pass_word
        # 日志定义
        self._Log = logging
        self._Log.basicConfig(level=logging.ERROR,
                              format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                              datefmt='%a, %d %b %Y %H:%M:%S'
                              )

    def __sftp_mul_process_deal_grandson__(self, ori_src_path, ori_dec_path, first_task_object,
                                           opera_method, task_que, task_event):
        """
        处理目标目录任务，遍历目录进行文件目录，根据put_get_flag标志进行文件的上传下载操作
        :param ori_src_path:
        :param ori_dec_path:
        :param first_task_object:
        :param opera_method:
        :param task_que:
        :param task_event:
        :return:
        """
        ssh = paramiko_sh.SSHConnection(self._HostIp, self._Port, self._UserName, self._PassWord)
        ssh.connect()
        if ssh._Sftp is None:
            # 获取SFTP实例
            ssh._Sftp = paramiko.SFTPClient.from_transport(ssh._Trans)
        self._Log.info('我是孙子进程,Run task PID(%s).PPID(%s)..' % (os.getpid(), os.getppid()))
        task_object = None
        while not task_event.is_set():
            try:
                if first_task_object is None:   # 没有第一个任务就需要取新的任务
                    task_object = task_que.get(timeout=1)
                else:   # 获取到第一个任务后就制空
                    task_object = first_task_object
                    first_task_object = None
                # 两秒超时，捕获异常去检测事件状态
                self._Log.info('队列目前的情况:%s' % task_que.qsize())
                # (file_path,file_name)=os.path.split(file_dir)
                start = time.time()
                opera_method(ssh, task_object, ori_src_path, ori_dec_path, task_que)
                end = time.time()
                self._Log.info('Task %s runs %0.2f seconds.' % (task_object, (end - start)))
                task_que.task_done()
            except my_queue.Empty: #这里检测是否收到了退出事件
                continue
            except Exception as err_msg:    # 报错后通知其他进程全部退出，暂时不考虑其他进程接管，防止死循环，后期再处理
                self._Log.error('[%ld]执行任务出错[%s],退出！' % (os.getpid(), err_msg))
                ssh.disconnect()
                #task_que.put(task_object)
                return False
        self._Log.info('孙子我已经收到了退出事件: %s' % os.getpid())
        ssh.disconnect()
        return True

    def __put_local_task__(self, ssh_class_object, task_object, ori_local_object, ori_remote_object, task_que):
        """
        将本地对象(文件/文件夹)上传到远端对象(文件夹/文件)
        :param ssh_class_object: SSH(SFTP)连接对象，用来使用sftp连接
        :param task_object:此时接收的任务对象
        :param ori_remote_object:原始传入的远程对象
        :param ori_local_object:原始传入的本地对象
        :return:
        """
        # 分离远程目标文件夹的名称
        (local_dir_path, local_dir_name) = os.path.split(ori_local_object)

        '''
        判断传入的是文件还是文件夹，文件直接下载，
        文件夹就先建立，而后遍历生成任务队列
        '''
        try:
            object_stat = os.stat(task_object)
            self._Log.info("exist [%s]" % task_object)
            if S_ISDIR(object_stat.st_mode):
                '''在远程建立文件夹
                '''
                remote_dir_new = ori_remote_object + os.path.sep + task_object[len(local_dir_path)+1:len(task_object)]
                # 如果有了就不用建立了，避免报错
                try:
                    ssh_class_object._Sftp.stat(remote_dir_new)
                except Exception as err_msg:
                    self._Log.info('[%s]远程建立:%s' % (err_msg, remote_dir_new))
                    ssh_class_object._Sftp.mkdir(remote_dir_new)
                object_list = os.listdir(task_object)
                for file in object_list:
                    remote_file_path = task_object + os.path.sep + file
                    task_que.put(remote_file_path)
            else:
                remote_file=ori_remote_object+os.path.sep+task_object[len(local_dir_path) + 1:len(task_object)]
                # 如果本地存在这个文件则删除，如果本地是目录，则直接放到对应的目录中
                self._Log.info('上传数据[%s][%s]' % (task_object,remote_file))
                ssh_class_object.sftp_put(task_object, remote_file)
        except Exception as err_msg:
            self._Log.error("上传数据错误 [%s]-[%s]" % (task_object, err_msg))
            return False
        return True

    def __get_remote_task__(self, ssh_class_object, file_object, ori_remote_dir, ori_local_dir, task_que):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        :param ssh_class_object:
        :param file_object:
        :param ori_remote_dir:
        :param ori_local_dir:
        :param task_que:
        :return:
        """
        # 分离远程目标文件夹的名称
        (ori_remote_dir_path, ori_remote_dir_name) = os.path.split(ori_remote_dir)

        '''
        判断传入的是文件还是文件夹，文件直接下载，
        文件夹就先建立，而后遍历生成任务队列
        '''
        try:
            object_stat = ssh_class_object._Sftp.stat(file_object)
            self._Log.info("exist [%s]" % file_object)
            if S_ISDIR(object_stat.st_mode):
                '''在本地建立文件夹
                '''
                local_dir_new = ori_local_dir + os.path.sep + file_object[len(ori_remote_dir_path)+1:len(file_object)]
                self._Log.info('本地建立:%s' % local_dir_new)
                os.makedirs(local_dir_new, exist_ok=True)
                object_list = ssh_class_object._Sftp.listdir_attr(file_object)
                for file in object_list:
                    remote_file_path = file_object + os.sep + file.filename
                    task_que.put(remote_file_path)
            else:
                local_file = ori_local_dir+os.path.sep+file_object[len(ori_remote_dir_path) + 1:len(file_object)]
                # 如果本地存在这个文件则删除，如果本地是目录，则直接放到对应的目录中
                self._Log.info('下载数据[%s][%s]' % (file_object, local_file))
                ssh_class_object.sftp_get(file_object, local_file)
        except Exception as err_msg:
            self._Log.error("下载数据错误 [%s]-[%s]" % (file_object, err_msg))
            return False
        return True

    def __sftp_mul_process_deal_son__(self, src_path, dec_path, process_num, opera_method, task_que, task_event):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        :param src_path:
        :param dec_path:
        :param process_num:
        :param opera_method:
        :param task_que:
        :param task_event:
        :return:
        """
        self._Log.info('定义任务多并发')
        process_list = []
        while not task_event.is_set():
            try:
                '''
                这里控制进程的开启数量，最大为定义的进程数(防止SFTP的连接过多)，
                开启进程的原则为：如果检测到任务有剩余，在定义范围内立即开启进程处理任务
                '''
                if len(process_list) < process_num:  # 小于最大定义数就开启进程
                    first_task_object = task_que.get(timeout=1)
                    if len(process_list)>10:
                        time.sleep(1)
                    process = multiprocessing.Process(target=self.__sftp_mul_process_deal_grandson__,
                                                      args=(src_path, dec_path, first_task_object, opera_method,
                                                            task_que, task_event))
                    process.start()
                    process_list.append(process)
                else:   # 达到最大进程数限制就不在建立新进程
                    break
            except Queue.Empty:     # 这里检测是否收到了退出事件
                    continue
            # 最后要将task_done将信息传给JION判断是否消费完毕
        self._Log.info('儿子我已经收到了退出事件: %s' % os.getpid())
        # 等待子任务退出
        for i in range(len(process_list)):
            process_list[i].join()

        self._Log.info('孙子已经退出完毕')

        return True

    @staticmethod
    def delete_object_sep(dec_object):
        """
        去掉目录最后的sep分割,windows为'\',Linux为'/'
        :param dec_object: 目标对象
        :return: 去掉sep的对象
        """
        if len(dec_object) == 0:
            return dec_object
        if dec_object[-1] == '\\' or dec_object[-1] == '/':
            dec_object = dec_object[0:-1]
        return dec_object

    def __sftp_mul_process_deal__(self, src_path, dec_path, process_num, opera_method):
        """
        这里统一定义队列、事件，用以控制开立的子进程、子子进程
        :param src_path: 源路径
        :param dec_path: 目标路径
        :param process_num: 最大进程数限制
        :param opera_method: 操作方式(下载/上传)
        :return:
        """
        '''
        对本地对象以及远程对象进行合法性判断
        '''
        src_path = self.delete_object_sep(src_path)
        dec_path = self.delete_object_sep(dec_path)
        '''
        检查传入参数的合法性，并进行处理
        '''
        if len(src_path) == 0 or len(dec_path) == 0:
            self._Log.error("路径存在空的情况![%s][%s]" % (src_path, dec_path))
            return False

        # 定义任务事件
        task_event = multiprocessing.Event()
        task_event.clear()

        # 定义任务队列
        queen = multiprocessing.Manager()
        task_que = queen.Queue()

        # 放入目标文件夹任务
        task_que.put(src_path)

        # 开启子进程进行任务分发，父进程进行任务监控
        self._Log.info('开启子进程进行任务分发，父进程进行任务监控')
        process = multiprocessing.Process(target=self.__sftp_mul_process_deal_son__,
                                          args=(src_path, dec_path, process_num, opera_method, task_que, task_event))
        process.start()
        self._Log.info('等待任务队列退出')
        task_que.join()
        self._Log.info("任务退出")

        # 通知任务进行着退出
        task_event.set()
        self._Log.info('通知所有进程退出')

        process.join()
        self._Log.info('所有进程全部退出')

        self._Log.info("主进程终止")

    def sftp_get_dir(self, remote_path, local_path, max_process_num=10):
        """
        下载远程文件夹或文件
        :param local_path:本地 相对/绝对的 文件/目录 路径
        :param remote_path:远端文件/目录绝对路径
        :param max_process_num: 最大sftp并发数限制
        :return:
        """
        # 取绝对路径
        local_path = os.path.abspath(local_path)
        # 选择执行的方法为put
        try:
            self.__sftp_mul_process_deal__(local_path, remote_path, max_process_num, self.__get_remote_task__)
        except Exception as err_msg:
            self._Log.error('下载失败[%s]' % err_msg)
            return False
        return True

    def sftp_put_dir(self, local_path, remote_path, max_process_num=10):
        """
        上传远程文件或文件夹
        :param local_path: 本地 相对/绝对的 文件/目录 路径
        :param remote_path: 远端文件/目录绝对路径
        :param max_process_num: 最大sftp并发数限制
        :return:
        """
        # 取绝对路径
        local_path = os.path.abspath(local_path)
        # 选择执行的方法为put
        try:
            self.__sftp_mul_process_deal__(local_path, remote_path, max_process_num, self.__put_local_task__)
        except Exception as err_msg:
            self._Log.error('上传失败[%s]' % err_msg)
            return False
        return True
