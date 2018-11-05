#README.txt
***环境是在Linux/Unix主机之间**** 
###需求 
1、一台主机无密码登录其他主机进行操作(如同:SCRT) 
2、不用登录其他主机就能实现主机命令执行 
3、远程下载、上传文件 
4、远程多并发上传、下载文件夹 
5、操作方式类似于Linux scp/ssh命令操作 

###主要使用工具及技术 
1、paramiko模块的shell、sftp、ssh相关功能； 
2、多进程并发； 
3、进程队列与事件的结合使用； 
4、使用到多进程子嵌套的方式完成功能； 
5、内置模块logging的使用； 

###工具使用方式及相关说明如下： 
python sh_stp_main.py -xsh account@192.168.1.1 (执行一个远程xshell终端) 
python sh_stp_main.py -sh account@192.168.1.1 'df -h' (执行远程shell命令并返回结果) 
python sh_stp_main.py -put 本地文件 account@192.168.1.1:远程文件/目录(上传文件到远程主机) 
python sh_stp_main.py -get account@192.168.1.1:远程文件 本地文件/目录(从远程主机下载文件) 
python sh_stp_main.py -putdir 本地文件/目录 account@192.168.1.1:远程文件/目录(上传文件/目录到远程主机) 
python sh_stp_main.py -getdir account@192.168.1.1:远程文件/目录 本地文件/目录(下载文件/目录到本地主机) 

在sh_stp_main.py的字典中定义主机相关信息；
