# coding=utf-8
# !/usr/bin/env python

# -*- encoding: utf-8 -*-

__author__ = 'yuanwm <ywmpsn@163.com>'

from stat import S_ISDIR
import os
import time
import multiprocessing
import sys
if sys.version > '3':
    import queue
    my_queue = queue
else:
    import Queue
    my_queue = Queue
    if sys.getdefaultencoding() != 'utf-8':
        reload(sys)
        sys.setdefaultencoding('utf-8')
# 由于多进程是封装单进程的SFTP，因此必须这里不使用继承，而采用二次封装调用
import paramiko_sh
import logging
import paramiko
import datetime


class MultiSftp(paramiko_sh.SSHConnection):
    def __init__(self, host_ip, port, user_name, pass_word):
        """
        初始化各类属性
        """
        # 兼容py2.x 3.x
        super(MultiSftp, self).__init__(host_ip, port, user_name, pass_word)

        self._HostIp = host_ip
        self._Port = port
        self._UserName = user_name
        self._PassWord = pass_word
        # 日志定义
        self._Log = logging
        self._Log.basicConfig(level=logging.ERROR,
                              format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                              datefmt='%a, %d %b %Y %H:%M:%S',
                              )

    def __sftp_mul_process_deal_grandson__(self, ori_src_top_path, ori_dec_path, first_task_object,
                                           opera_method, task_que, task_que_dir, task_que_file,
                                           task_event, task_event_file,
                                           task_que_file_size, task_que_running):
        """
        处理目标目录任务，遍历目录进行文件目录，根据put_get_flag标志进行文件的上传下载操作
        :param ori_src_top_path:
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
        self._Log.info('我是孙子进程,Run task PID({}).PPID({})..'.format(os.getpid(), os.getppid()))
        task_object = None

        # 文件、目录任务搜寻
        while not task_event.is_set():
            try:
                if first_task_object is None:   # 没有第一个任务就需要取新的任务
                    task_object = task_que.get(timeout=1)
                else:   # 获取到第一个任务后就置空
                    task_object = first_task_object
                    first_task_object = None
                # 两秒超时，捕获异常去检测事件状态
                self._Log.info('队列目前的情况:{}'.format(task_que.qsize()))
                # (file_path,file_name)=os.path.split(file_dir)
                start = time.time()
                opera_method(ssh, task_object, ori_src_top_path, ori_dec_path, task_que,
                                task_que_dir=task_que_dir, task_que_file=task_que_file,
                                task_que_file_size=task_que_file_size)
                end = time.time()
                self._Log.info('Task {} runs {:.2f} seconds.'.format(task_object, (end - start)))
                task_que.task_done()
            except my_queue.Empty:  # 这里检测是否收到了退出事件
                continue
            except Exception as err_msg:    # 报错后通知其他进程全部退出，暂时不考虑其他进程接管，防止死循环，后期再处理
                ssh.disconnect()
                raise ChildProcessError('文件搜寻[{}]执行任务[{}]出错[{}],退出！'.format(
                    os.getpid(),task_object,err_msg))

        # 文件下载任务
        while not task_event_file.is_set():
            try:
                if first_task_object is None:   # 没有第一个任务就需要取新的任务
                    task_object = task_que_file.get(timeout=1)
                else:   # 获取到第一个任务后就置空
                    task_object = first_task_object
                    first_task_object = None
                # 能走到这都算是已经在处理了
                task_que_running.put(task_object)
                # 两秒超时，捕获异常去检测事件状态
                self._Log.info('队列目前的情况:{}'.format(task_que_file.qsize()))
                # (file_path,file_name)=os.path.split(file_dir)
                start = time.time()
                opera_method(ssh, task_object, ori_src_top_path, ori_dec_path, task_que_file,
                             task_que_file = None,task_que_file_size = task_que_file_size)
                end = time.time()
                self._Log.info('Task {} runs {:.2f} seconds.'.format(task_object, (end - start)))
                task_que_file.task_done()
                # 暂时只管数目，不管取出来的是否是原来的文件名
                tmp_running_name = task_que_running.get()  # 原则上这里不会超时
            except my_queue.Empty:  # 这里检测是否收到了退出事件
                continue
            except Exception as err_msg:    # 报错后通知其他进程全部退出，暂时不考虑其他进程接管，防止死循环，后期再处理
                ssh.disconnect()
                # 暂时只管数目，不管取出来的是否是原来的文件名
                tmp_running_name = task_que_running.get()  # 原则上这里不会超时
                raise ChildProcessError('文件下载[{}]执行任务[{}]出错[{}],退出！'.format(
                    os.getpid(), task_object, err_msg))

        self._Log.info('孙子我已经收到了退出事件: {}'.format(os.getpid()))
        ssh.disconnect()

    def __put_local_task__(self, ssh_class_object, task_object, local_top_path, ori_remote_object,
                           task_que, task_que_dir=None, task_que_file=None, task_que_file_size=None):
        """
        将本地对象(文件/文件夹)上传到远端对象(文件夹/文件)
        :param ssh_class_object: SSH(SFTP)连接对象，用来使用sftp连接
        :param task_object:此时接收的任务对象
        :param ori_remote_object:原始传入的远程对象
        :param task_que:任务队列
        :return:
        """

        '''
        判断传入的是文件还是文件夹，文件直接下载，
        文件夹就先建立，而后遍历生成任务队列
        '''
        object_stat = os.stat(task_object)
        self._Log.info("exist [{}]".format(task_object))
        if S_ISDIR(object_stat.st_mode):
            '''在远程建立文件夹
            '''
            # 这是任务搜索，只加入列表不作其他操作
            if task_que_dir is not None:
                remote_dir_new = ori_remote_object + os.path.sep + task_object[
                                                                   len(local_top_path) + 1:len(task_object)]
                # 如果有了就不用建立了，避免报错
                try:
                    object_stat = ssh_class_object._Sftp.stat(remote_dir_new)
                    self._Log.info("exist [()]".format(remote_dir_new))
                    if not S_ISDIR(object_stat.st_mode):
                        raise TypeError('[{}]是文件,不能建立目录[{}]:{}'.format(remote_dir_new, remote_dir_new))
                except IOError as err_msg:
                    self._Log.info('没有目录[{}]远程建立:{}'.format(remote_dir_new, remote_dir_new))
                    ssh_class_object._Sftp.mkdir(remote_dir_new)
                task_que_dir.put(task_object)
                # 任务搜索的下级遍历
                object_list = os.listdir(task_object)
                for file in object_list:
                    remote_file_path = task_object + os.path.sep + file
                    task_que.put(remote_file_path)
        else:
            # 这是任务搜索，只加入列表不作其他操作
            if task_que_file is not None:
                # 这里一定要先大小在文件，因为监控是以文件去取大小
                # 获取文件的大小
                task_que_file_size.put(object_stat.st_size)
                # 文件名
                task_que_file.put(task_object)
                return
            remote_file = ori_remote_object + os.path.sep + task_object[len(local_top_path) + 1:len(task_object)]
            # 如果本地存在这个文件则删除，如果本地是目录，则直接放到对应的目录中
            self._Log.info('上传数据[{}][{}]'.format(task_object, remote_file))
            tmp_list=[]
            tmp_list.append(task_object)
            if ssh_class_object.sftp_put(tmp_list, remote_file, callback_object=task_que_file_size) is False:
                raise IOError("文件上传失败[{}]".format(task_object))

    def __get_remote_task__(self, ssh_class_object, file_object, remote_top_path, ori_local_dir,
                            task_que, task_que_dir=None, task_que_file=None, task_que_file_size=None):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        :param ssh_class_object:
        :param file_object:
        :param remote_top_path:
        :param ori_local_dir:
        :param task_que:
        :return:
        """
        '''
        判断传入的是文件还是文件夹，文件直接下载，
        文件夹就先建立，而后遍历生成任务队列
        '''
        object_stat = ssh_class_object._Sftp.stat(file_object)
        self._Log.info("exist [{}]".format(file_object))
        if S_ISDIR(object_stat.st_mode):
            '''在本地建立文件夹
            '''
            # 这是任务搜索，只加入列表不作其他操作
            if task_que_dir is not None:
                local_dir_new = ori_local_dir + os.path.sep + file_object[len(remote_top_path) + 1:len(file_object)]
                self._Log.info('本地建立:{}'.format(local_dir_new))
                os.makedirs(local_dir_new, exist_ok=True)
                task_que_dir.put(file_object)
                # 下级目录搜索
                object_list = ssh_class_object._Sftp.listdir_attr(file_object)
                for file in object_list:
                    remote_file_path = file_object + os.sep + file.filename
                    task_que.put(remote_file_path)
        else:
            # 这是任务搜索，只加入列表不作其他操作
            if task_que_file is not None:
                # 这里一定要先大小在文件，因为监控是以文件去取大小
                # 获取文件的大小
                task_que_file_size.put(object_stat.st_size)
                task_que_file.put(file_object)
                return
            local_file = ori_local_dir + os.path.sep + file_object[len(remote_top_path) + 1:len(file_object)]
            # 如果本地存在这个文件则删除，如果本地是目录，则直接放到对应的目录中
            self._Log.info('下载数据[{}][{}]'.format(file_object, local_file))
            ssh_class_object.sftp_get(file_object, local_file, callback_object=task_que_file_size)

    def __sftp_mul_process_deal_son__(self, src_path, dec_path, process_num, opera_method,
                                      task_que, task_que_dir, task_que_file,
                                      task_event, task_event_file, task_que_file_size, task_que_running):
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

        # 搜寻任务
        while not task_event.is_set():
            try:
                '''
                这里控制进程的开启数量，最大为定义的进程数(防止SFTP的连接过多)，
                开启进程的原则为：如果检测到任务有剩余，在定义范围内立即开启进程处理任务
                '''
                if len(process_list) < process_num:  # 小于最大定义数就开启进程
                    first_task_object = task_que.get(timeout=1)
                    if len(process_list) > 10:
                        time.sleep(1)
                    process = multiprocessing.Process(target=self.call_sftp_mul_process_deal_grandson,
                                                      args=(src_path, dec_path, first_task_object, opera_method,
                                                            task_que, task_que_dir, task_que_file,
                                                            task_event, task_event_file,
                                                            task_que_file_size, task_que_running))
                    process.start()
                    process_list.append(process)
                else:   # 达到最大进程数限制就不在建立新进程
                    break
            except my_queue.Empty:     # 这里检测是否收到了退出事件
                continue
            except Exception as err_msg:
                # 停所有子进程以及其后的事件
                task_event.set()
                task_event_file.set()
                raise
        # 文件下载任务
        while not task_event_file.is_set():
            try:
                '''
                这里控制进程的开启数量，最大为定义的进程数(防止SFTP的连接过多)，
                开启进程的原则为：如果检测到任务有剩余，在定义范围内立即开启进程处理任务
                '''
                if len(process_list) < process_num:  # 小于最大定义数就开启进程
                    first_task_object = task_que_file.get(timeout=1)
                    if len(process_list) > 10:
                        time.sleep(1)
                    process = multiprocessing.Process(target=self.call_sftp_mul_process_deal_grandson,
                                                      args=(src_path, dec_path, first_task_object, opera_method,
                                                            task_que, task_que_dir, task_que_file,
                                                            task_event, task_event_file,
                                                            task_que_file_size, task_que_running))
                    process.start()
                    process_list.append(process)
                else:   # 达到最大进程数限制就不在建立新进程
                    break
            except my_queue.Empty:     # 这里检测是否收到了退出事件
                    continue
            except Exception as err_msg:
                # 停所有子进程以及其后的事件
                task_event_file.set()
                raise
        # 最后要将task_done将信息传给JION判断是否消费完毕
        self._Log.info('儿子我已经收到了退出事件: {}'.format(os.getpid()))
        # 等待子任务退出
        for i in range(len(process_list)):
            process_list[i].join()

        self._Log.info('孙子已经退出完毕')



    def __sftp_mul_process_deal__(self, src_path_list, dec_path, process_num, opera_method, file_macth_in):
        """
        这里统一定义队列、事件，用以控制开立的子进程、子子进程
        :param src_path_list: 源路径列表
        :param dec_path: 目标路径
        :param process_num: 最大进程数限制
        :param opera_method: 操作方式(下载/上传)
        :param file_macth_in: 文件的匹配符
        :return:
        """
        '''
        对本地对象以及远程对象进行合法性判断
        '''
        dec_path = self.delete_object_sep(dec_path)
        '''
        检查传入参数的合法性，并进行处理
        '''
        if len(dec_path) == 0:
            raise ValueError("路径存在空的情况![{}]".format(dec_path))

        # 定义搜寻任务事件
        task_event = multiprocessing.Event()
        task_event.clear()

        # 定义文件下载任务事件
        task_event_file = multiprocessing.Event()
        task_event_file.clear()

        # 定义任务队列
        queen = multiprocessing.Manager()
        task_que = queen.Queue()

        # 定义目录任务队列
        queen = multiprocessing.Manager()
        task_que_dir = queen.Queue()

        # 定义文件任务队列
        queen = multiprocessing.Manager()
        task_que_file = queen.Queue()

        # 定义传输数据大小任务队列，用于监控
        queen = multiprocessing.Manager()
        task_que_file_size = queen.Queue()

        # 定义正在处理的文件下载任务，用于监控
        queen = multiprocessing.Manager()
        task_que_running = queen.Queue()

        # 放入目标文件夹任务
        if len(src_path_list) == 0:
            raise ValueError("路径列表存在空的情况![{}]".format(src_path_list))
        tmp_src_path = ''
        for tmp_src_path in src_path_list:
            tmp_src_path = self.delete_object_sep(tmp_src_path)
            task_que.put(tmp_src_path)
        # 获取最后一个的路径的上级路径作为顶层目录，分离远程目标文件夹的名称
        (top_src_path, top_src_name) = os.path.split(tmp_src_path)

        # 开启子进程进行任务分发，父进程进行任务监控
        process_list = []
        # 先开启一个任务处理进程
        self._Log.info('开启子进程进行任务分发，父进程进行任务监控')
        process = multiprocessing.Process(target=self.call_sftp_mul_process_deal_son,
                                          args=(top_src_path, dec_path, process_num, opera_method,
                                                task_que, task_que_dir, task_que_file,
                                                task_event, task_event_file, task_que_file_size, task_que_running))
        process.start()
        process_list.append(process)

        # 开启一个任务监控进程
        process_view = multiprocessing.Process(target=self.call_sftp_mul_view_bar,
                                          args=(task_que_dir, task_que_file,
                                                task_event, task_event_file,
                                                task_que_file_size, task_que_running, file_macth_in))
        process_view.start()
        process_list.append(process_view)
        self._Log.info('等待搜寻任务队列退出')
        task_que.join()
        self._Log.info("任务退出")

        # 这里必须要等待监控将队列里面的数据取完了才能进行下一步;或者被子进程自己终止事件
        while (task_que_file_size.qsize() > 0 or task_que_running.qsize() > 0) and not task_event.is_set():
            time.sleep(1)

        # 通知搜寻任务退出
        task_event.set()
        self._Log.info('通知搜寻任务退出')

        self._Log.info('等待文件下载任务队列退出')
        task_que_file.join()
        self._Log.info("任务退出")

        # 这里必须要等待监控将队列里面的数据取完了才能进行下一步
        while (task_que_file_size.qsize() > 0 or task_que_running.qsize() > 0) and not task_event_file.is_set():
            time.sleep(1)

        # 通知文件下载任务退出
        task_event_file.set()
        self._Log.info('通知文件下载任务退出')

        for i in range(len(process_list)):
            process_list[i].join()
        self._Log.info('所有进程全部退出')

        self._Log.info("主进程终止")

    def sftp_get_dir(self, remote_path_in, local_path_in, max_process_num=10):
        """
        下载远程文件夹或文件
        :param local_path_in:本地 相对/绝对的 文件/目录 路径
        :param remote_path_in:远端文件/目录绝对路径
        :param max_process_num: 最大sftp并发数限制
        :return:
        """

        # 清理'/'符号
        local_path = self.delete_object_sep(local_path_in)
        remote_path = self.delete_object_sep(remote_path_in)

        # 取匹配符用于监控
        (tmp_remote_path, tmp_remote_file_macth)=os.path.split(remote_path)

        # 取绝对路径，并进行分离
        local_path = os.path.abspath(local_path)
        ssh = paramiko_sh.SSHConnection(self._HostIp, self._Port, self._UserName, self._PassWord)
        ssh.connect()

        # 解析文件列表
        remote_path_list = ssh.remote_path_parse(remote_path)

        # 如果解析出的只含有一个且为文件，则直接调用文件sftp接口
        if len(remote_path_list) == 1:
            tmp_remote_object = remote_path_list[0]     # 直接取第一个
            local_object_stat = ssh.judge_remote_path_stat(tmp_remote_object)
            if S_ISDIR(local_object_stat) is False:   # 非目录类型直接上传处理
                try:
                    ssh.sftp_get(tmp_remote_object, local_path)
                    ssh.disconnect()
                    return
                except Exception:
                    ssh.disconnect()
                    raise

        # 走到这里说明是多个或者文件目录
        # 选择执行的方法为put
        try:
            self.__sftp_mul_process_deal__(remote_path_list, local_path, max_process_num,
                                            self.__get_remote_task__, tmp_remote_file_macth)
        except Exception:
            raise

    def sftp_put_dir(self, local_path_list_in, remote_path_in, max_process_num=10):
        """
        上传远程文件或文件夹
        :param local_path_in: 本地 相对/绝对的 文件/目录 路径
        :param remote_path_in: 远端文件/目录绝对路径
        :param max_process_num: 最大sftp并发数限制
        :return:
        """

        # 清理'/'符号
        remote_path = self.delete_object_sep(remote_path_in)

        # 取匹配符用于监控
        #(tmp_remote_path, tmp_local_file_macth)=os.path.split(local_path_in)

        # 取绝对路径，并进行分离
        #local_path = os.path.abspath(local_path)
        ssh = paramiko_sh.SSHConnection(self._HostIp, self._Port, self._UserName, self._PassWord)
        ssh.connect()
        # 解析文件列表
        #local_path_list = ssh.local_path_parse(local_path)
        # 本地文件路径绝对化
        local_path_list=[]
        for tmp_path in local_path_list_in:
            local_path_list.append(os.path.abspath(tmp_path))

        self._Log.info('文件列表[{}]'.format(local_path_list))

        # 如果解析出的只含有一个且为文件，则直接调用文件sftp接口
        if len(local_path_list) == 1:
            tmp_local_object = local_path_list[0]   # 直接取第一个
            local_object_stat = ssh.judge_local_path_stat(tmp_local_object)
            if S_ISDIR(local_object_stat) is False:   # 非目录类型直接上传处理
                try:
                    ssh.sftp_put(local_path_list, remote_path)
                    ssh.disconnect()
                    return
                except Exception:
                    ssh.disconnect()
                    raise
        # 走到这里说明是多个或者文件目录
        if len(local_path_list) == 1:
            (tmp_remote_path, tmp_local_file_macth)=os.path.split(local_path_list[0])
        else:
            tmp_local_file_macth = 'multi_file_process'
        try:
            self.__sftp_mul_process_deal__(local_path_list, remote_path, max_process_num,
                                                self.__put_local_task__, tmp_local_file_macth)
        except Exception:
            raise

    def __sftp_mul_view_bar__(self, task_que_dir, task_que_file, task_event, task_event_file,
                              task_que_file_size, task_que_running, file_macth_in):

        """"
        统计间隔时间1s
        """

        # 需要用到的变量提前定义
        task_total_file_num = 0
        task_total_dir_num = 0
        task_cur_file_num = 0
        task_file_total_size = 0
        task_file_cur_size = 0
        task_up_file_size = 0
        task_beigin_time = datetime.datetime.now()  #这个时间约为开始时间
        up_deal_time = task_beigin_time
        running_task_file = 0

        # 搜寻任务
        while not task_event.is_set():
            try:
                '''
                搜寻任务运行时，需要统计文件夹个数，文件个数，当前文件的总大小，阶段：search
                '''
                # 文件大小统计
                task_total_dir_num = task_que_dir.qsize()
                task_total_file_num = task_que_file.qsize()
                # 这里可能与统计的文件个数有点差异，但是概率极小；如果通过新增文件个数的判别可以解决这个问题，但个人觉得没有那个必要
                new_file_num = task_que_file_size.qsize()
                # 获取了多少文件就要从大小列表中进行统计
                for i in range(new_file_num):
                    try:
                        tmp_file_size = task_que_file_size.get(timeout=0.1)   #   原则上这里不会超时
                        task_file_total_size += tmp_file_size
                    except my_queue.Empty:  # 这里检测是否收到了退出事件
                        continue
                task_cur_file_num = 0
                task_cur_time = datetime.datetime.now()
                self.mult_view_bar(file_macth_in, task_total_dir_num, task_cur_file_num, task_total_file_num,
                                   task_file_cur_size, task_file_total_size, task_up_file_size,
                                   up_deal_time, task_cur_time, task_beigin_time, running_task_file, show_rate=False)
                task_up_file_size = task_file_cur_size
                up_deal_time = task_cur_time
                time.sleep(0.1)
            except my_queue.Empty:     # 这里检测是否收到了退出事件
                continue
                # 文件下载任务
        while not task_event_file.is_set() or task_que_file_size.qsize() > 0 or task_que_running.qsize() > 0:
            try:
                '''
                搜寻任务运行时，需要统计文件夹个数，文件个数，当前文件的总大小，阶段：create_file
                '''
                # 文件大小统计
                # 由于队列中可能有多个值，因此，这里先统计一次大小，然后取指定大小的数据之和即可；
                task_cur_time = datetime.datetime.now() # 获取统计时间
                tmp_que_file_size = task_que_file_size.qsize()
                for i in range(tmp_que_file_size):
                    try:
                        tmp_file_size = task_que_file_size.get(timeout=0.1)   # 原则上这里不会超时
                        task_file_cur_size += tmp_file_size
                    except my_queue.Empty:  # 这里检测是否收到了退出事件
                        continue
                # 由于running_task是由执行任务的进程进行处理，因此为0时可能监控未获取，但是只要大小相同，则认定running_task为0；
                if task_file_cur_size == task_file_total_size:
                    running_task_file = 0
                else:
                    running_task_file = task_que_running.qsize()
                task_cur_file_num = task_total_file_num-task_que_file.qsize()-running_task_file
                self.mult_view_bar(file_macth_in, task_total_dir_num, task_cur_file_num,
                                   task_total_file_num, task_file_cur_size, task_file_total_size, task_up_file_size,
                                   up_deal_time, task_cur_time, task_beigin_time, running_task_file)
                task_up_file_size = task_file_cur_size
                up_deal_time = task_cur_time
                time.sleep(2)
            except my_queue.Empty:     # 这里检测是否收到了退出事件
                continue
        # 这里文件目录与文件都已经搜索完毕,如果文件总数为0直接显示处理为百分之百即可
        if task_total_file_num == 0:
            task_cur_time = datetime.datetime.now()
            self.mult_view_bar(file_macth_in, task_total_dir_num, task_cur_file_num, task_total_file_num,
                              task_file_cur_size, task_file_total_size, task_up_file_size,
                              up_deal_time, task_cur_time, task_beigin_time, running_task_file, show_rate=True)

        sys.stdout.write('\n')
        sys.stdout.flush()
        # 最后要将task_done将信息传给JION判断是否消费完毕
        self._Log.info('监控显示我已经收到了退出事件: {}'.format(os.getpid()))

        return True

    def mult_view_bar(self, run_stage, total_dir_num, cur_file_num, total_file_num,
                      cur_file_size, total_file_size, up_file_size, up_deal_time, task_cur_time_in,
                      task_beigin_time, running_task_file, show_rate=True):
        """
        进度显示,暂定样式:
        任务匹配名    [======]    100%    24   1500[当前正在处理的任务]/3000(文件传输)     35kb/36kb    35KB/s  00:00:00(预计剩余时间)   00:00:00(花费总时间)
        这里计算过多，会造成传输的延迟。
        :param cur_file_size:当前文件大小
        :param total_file_size:文件总大小
        :param src_file_name
        :return:
        """
        # 进度条比例（***这里可以自定义修改*******）
        sum_process = 10

        # 初始数据获取
        task_begin_time_in = task_beigin_time

        # 获取上一次的时间
        task_up_time_in = up_deal_time

        # 获取上一次的大小
        up_file_size = up_file_size

        # 比例(数据大小>文件>文件夹)
        if show_rate is False:
            rate = 0
        elif total_file_size != 0:
            rate = cur_file_size / total_file_size
        elif total_file_num != 0:
            rate = cur_file_num / total_file_num
        else:
            rate = 1
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

        # 计算速率
        if cur_spend_time_seconds == 0:
            speed_rate = 0
        else:
            speed_rate = int((cur_file_size - up_file_size) / cur_spend_time_seconds)

        # 计算后的展示
        show_speed_rate = paramiko_sh.SSHConnection.converting_bytes(speed_rate)

        # 计算预计剩余时间
        if speed_rate == 0:
            pre_spend_time_second = 0
        else:
            pre_spend_time_second = int((total_file_size - cur_file_size) / speed_rate)  # 秒
        ori_old_time_arry = time.localtime(0)  # 最原始时间:一般1970
        pre_spend_time_arry = time.localtime(pre_spend_time_second)

        # 进行转换计算
        ori_old_time = time.strftime("%Y-%m-%d %H:%M:%S", ori_old_time_arry)
        pre_spend_time_tmp = time.strftime("%Y-%m-%d %H:%M:%S", pre_spend_time_arry)
        pre_spend_time = datetime.datetime.strptime(pre_spend_time_tmp, '%Y-%m-%d %H:%M:%S') - \
                         datetime.datetime.strptime(ori_old_time, '%Y-%m-%d %H:%M:%S')

        # 大小转换为b/kb/M/GB
        show_total_file_size = paramiko_sh.SSHConnection.converting_bytes(total_file_size)
        show_cur_file_size = paramiko_sh.SSHConnection.converting_bytes(cur_file_size)

        show_dir_rate = "%s" % (total_dir_num)
        show_file_rate = " %s[%s]/%s" % (cur_file_num, running_task_file, total_file_num)
        show_size_rate = "%s/%s" % (show_cur_file_size, show_total_file_size)

        try:
            file_name_len = os.get_terminal_size().columns-110
        except OSError:
            file_name_len = 40
        if len(run_stage) < file_name_len:
            file_name_show="{}{}".format(run_stage, (file_name_len-len(run_stage)) * " ")
        else:
            file_name_show="{} ".format(run_stage)
        show_percent='{}%'.format(rate_percent)
        r = '\r%s%-6s%22s%15s/s%10s%10s%8s%17s' % (file_name_show,show_percent,
                                                    show_size_rate,show_speed_rate,
                                                    pre_spend_time, spend_time, show_dir_rate, show_file_rate)
        if show_rate is False:
            sys.stdout.write('{}'.format(r))
        else:
            sys.stdout.write('{}\n'.format(r))
        sys.stdout.flush()

    @staticmethod
    def delete_object_sep(dec_object):
        """
        去掉目录最后的sep分割,windows为'\',Linux为'/'，此处无windows
        :param dec_object: 目标对象
        :return: 去掉sep的对象
        """
        if len(dec_object) == 0:
            return dec_object
        if dec_object[-1] == '\\' or dec_object[-1] == '/':
            dec_object = dec_object[0:-1]
        return dec_object

    # 子进程函数调用处理
    def call_sftp_mul_view_bar(self, task_que_dir, task_que_file, task_event, task_event_file,
                                  task_que_file_size, task_que_running, file_macth_in):
        try:
            self.__sftp_mul_view_bar__(task_que_dir, task_que_file, task_event, task_event_file,
                                  task_que_file_size, task_que_running, file_macth_in)
        except Exception as err_msg:
            sys.stderr.write('{}'.format(err_msg))
            sys.stdout.flush()
            return
    # 子进程函数调用处理
    def call_sftp_mul_process_deal_grandson(self, ori_src_top_path, ori_dec_path, first_task_object,
                                           opera_method, task_que, task_que_dir, task_que_file,
                                           task_event, task_event_file,
                                           task_que_file_size, task_que_running):
        try:
            self.__sftp_mul_process_deal_grandson__(ori_src_top_path, ori_dec_path, first_task_object,
                                           opera_method, task_que, task_que_dir, task_que_file,
                                           task_event, task_event_file,
                                           task_que_file_size, task_que_running)
        except Exception as err_msg:
            sys.stderr.write('{}'.format(err_msg))
            sys.stdout.flush()
            return

    # 子进程函数调用处理
    def call_sftp_mul_process_deal_son(self, src_path, dec_path, process_num, opera_method,
                                      task_que, task_que_dir, task_que_file,
                                      task_event, task_event_file, task_que_file_size, task_que_running):
        try:
            self.__sftp_mul_process_deal_son__(src_path, dec_path, process_num, opera_method,
                                       task_que, task_que_dir, task_que_file,
                                       task_event, task_event_file, task_que_file_size, task_que_running)
        except Exception as err_msg:
            sys.stderr.write('{}'.format(err_msg))
            sys.stdout.flush()
            return