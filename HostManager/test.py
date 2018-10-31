from multiprocessing import Pool
import os, time
#需要使用进程Queue
from multiprocessing import Queue
import sys
import pickle
import paramiko_ssh
qq = Queue()
qq.put('/Users/yuanwm/Code/OldBoyPythonLearnProject/HostManager/test')
from paramiko_ssh import SSHConnection


def long_time_task(file, class_object):
    # print(file)
    # (file_path, qq)=file)
    print('Run task %s (%s)...' % (file, os.getpid()))
    start = time.time()
    print('test')
    class_object.get_remote_dir_all_files(file)
    end = time.time()
    print('Task %s runs %0.2f seconds.' % (file, (end - start)))

class someClass(object):

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
       self._Que = None
       self._Pool = None

   def gci(self, filepath):
       # 遍历filepath下所有文件，包括子目录
       print(filepath)
       if os.path.isdir(filepath):
           files = os.listdir(filepath)
           for fi in files:
               # print(os.path.join(filepath, fi))
               qq.put(os.path.join(filepath, fi))
       else:
           print('下载文件[%s]' % os.path.join(filepath))

   def Bar(arg):
       print('-->exec done:', arg, os.getpid())


   #def go(self):
   #   self.p = multiprocessing.Pool(4)
    #  self.p.apply_async(self.f, ('4',))


if __name__=='__main__':
    print('Parent process %s.' % os.getpid())
    p = Pool(1)
    sc = SSHConnection('192.168.1.7', '22', 'account', 'ie5Pxi$t')
    sc.connect()
    while True:
        print('等待接收......')
        file_path=qq.get()
        print('打开文件[%s]' % file_path)
        pid=1
        p.apply_async(long_time_task, args=(file_path,sc))
    print('Waiting for all subprocesses done...')
    p.close()
    p.join()
    print('All subprocesses done.')