import socket
import json
import sys
import time
import threading
import struct
sys.path.insert(1,".")  # 把上一级目录加入搜索路径
from DASP.module import DaspCommon, Task

class BaseServer(DaspCommon):
    '''基础服务器

    Dsp基础服务器

    属性:
        TaskDict: 任务字典
    '''
    TaskDict = {}

    def __init__(self):
        pass

    def recv_short_conn(self, host, port):
        '''
        短连接循环接收数据框架
        '''   
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        server.listen(100) #接收的连接数
        while True:
            conn, addr = server.accept()
            # print('Connected by', addr)
            headPack,body = self.recv_length(conn)
            self.MessageHandle(headPack,body,conn)
            conn.close()
               

    def recv_long_conn(self, host, port, adjID = ""):
        """
        长连接循环接收数据框架
        """
        while True:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind((host, port))
            server.listen(1) #接收的连接数
            conn, addr = server.accept()
            print('Connected by', addr)
            # FIFO消息队列
            dataBuffer = bytes()
            with conn:
                while True:
                    try:
                        data = conn.recv(1024)
                    except Exception as e:
                        # 发送端进程被杀掉
                        self.DisconnectHandle(adjID)
                        break
                    if data == b"":
                        # 发送端close()
                        self.DisconnectHandle(adjID)
                        break
                    if data:
                        # 把数据存入缓冲区，类似于push数据
                        dataBuffer += data
                        while True:
                            if len(dataBuffer) < self.headerSize:
                                break  #数据包小于消息头部长度，跳出小循环
                            # 读取包头
                            headPack = struct.unpack(self.headformat, dataBuffer[:self.headerSize])
                            bodySize = headPack[1]
                            if len(dataBuffer) < self.headerSize+bodySize :
                                break  #数据包不完整，跳出小循环
                            # 读取消息正文的内容
                            body = dataBuffer[self.headerSize:self.headerSize+bodySize]
                            body = body.decode()
                            # 数据处理
                            self.MessageHandle(headPack, body, conn)
                            # 数据出列
                            dataBuffer = dataBuffer[self.headerSize+bodySize:] # 获取下一个数据包，类似于把数据pop出

    def MessageHandle(self, headPack, body, conn):
        """
        数据处理函数,子类可重构该函数
        """
        if headPack[0] == 1:
            print(body)
        else:
            print("非POST方法")

    def DisconnectHandle(self, adjID):
        """
        对邻居断开连接的操作函数               
        """
        print (adjID , "已断开")      

    def connect(self,host1,port1,host2,port2,adjID,DAPPname):
        """
        发送连接请求
        如果没连上则改邻居不在线；如果连接上并收到connect回应，则加入子节点中
        """
        data = {
            "key": "connect",
            "host": host1,
            "port": port1,
            "id": DaspCommon.nodeID,
            "GUIinfo": DaspCommon.GUIinfo,
            "DAPPname": DAPPname
        }
        try:
            print ("connecting to {}:{}".format(host2,str(port2)))
            if DaspCommon.adjConnectFlag[DaspCommon.adjID.index(adjID)] == 0:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) #在客户端开启心跳维护
                sock.ioctl(socket.SIO_KEEPALIVE_VALS,(1,1*1000,1*1000)) #开始保活机制，60s后没反应开始探测连接，30s探测一次，一共探测10次，失败则断开
                remote_ip = socket.gethostbyname(host2)
                sock.connect((remote_ip, port2))

                DaspCommon.adjConnectFlag[DaspCommon.adjID.index(adjID)] = 1
                DaspCommon.adjSocket[adjID] = sock
            
            self.sendall_length(DaspCommon.adjSocket[adjID], data)
            headPack,body = self.recv_length(DaspCommon.adjSocket[adjID])
            jres = json.loads(body)
            if jres['key'] == 'connect':
                BaseServer.TaskDict[DAPPname].sonID.append(jres["id"])
                indext = DaspCommon.adjID.index(jres["id"])
                BaseServer.TaskDict[DAPPname].sonDirection.append(self.adjDirection[indext])
                BaseServer.TaskDict[DAPPname].CreateTreeSonFlag.append(0)
                BaseServer.TaskDict[DAPPname].sonData.append([])
            return 0
        except Exception as e:
            self.sendRunDatatoGUI("与邻居节点"+adjID+"连接失败", DAPPname) 
            print ("与邻居节点"+adjID+"连接失败")
            return adjID
                    
    def reconnect(self,host1,port1,host2,port2,adjID,direction):
        """
        发送重新连接请求
        """
        data = {
            "key": "reconnect",
            "host": host1,
            "port": port1,
            "id": DaspCommon.nodeID,
            "applydirection": direction
        }
        try:
            print ("{}:{} reconnecting to {}:{}".format(host1,str(port1),host2,str(port2)))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_ip = socket.gethostbyname(host2)
            sock.connect((remote_ip, port2))
            cont = "POST / HTTP/1.1\r\n"
            jsondata = json.dumps(data)
            self.sendall_length(sock, cont, jsondata)
            sock.close()
        except Exception as e:
            self.sendRunDatatoGUI("与邻居节点"+adjID+"连接失败") 
            print ("与邻居节点"+adjID+"连接失败")
            return adjID

    def send(self,id,data):
        """
        通过TCP的形式将信息发送至指定ID的节点
        """
        try:
            self.sendall_length(DaspCommon.adjSocket[id], data)
        except Exception as e:
            print ("与邻居节点{}连接失败".format(id))
            self.deleteadjID(id)
            self.deleteTaskDictadjID(id)
            self.sendRunDatatoGUI("与邻居节点{0}连接失败，已删除和{0}的连接".format(id)) 
    
    def Forward2sonID(self, jdata, DAPPname):
        """
        将json消息转发给子节点
        """
        if BaseServer.TaskDict[DAPPname].sonID:
            sjdata = json.dumps(jdata)
            for ele in reversed(BaseServer.TaskDict[DAPPname].TaskIPlist):
                if ele:
                    if ele[4] in BaseServer.TaskDict[DAPPname].sonID:
                        self.send(ele[4], data=sjdata)

    def deleteTaskDictadjID(self, id):  
        """
        删除本节点的任务和指定id邻居节点的所有连接(任务字典中的变量)
        """
        for key in BaseServer.TaskDict:
            BaseServer.TaskDict[key].deleteTaskadjID(id)
                
    def sendRunDatatoGUI(self, info, DAPPname = "system"):
        """
        通过UDP的形式将运行信息发送至GUI
        """
        self.sendtoGUIbase(info, "RunData", DAPPname)

    def sendEndDatatoGUI(self, info, DAPPname = "system"):
        """
        通过UDP的形式将结束信息发送至GUI
        """
        self.sendtoGUIbase(info, "EndData", DAPPname)

    def sendFlagtoGUI(self, info, DAPPname = "system"):
        """
        通过UDP的形式将运行状态发送至GUI  
        #0 未启动
        #1 暂停中
        #2 运行中
        """
        self.sendtoGUIbase(info, "RunFlag", DAPPname)

     

class TaskServer(BaseServer):
    """外部交互服务器
    
    用于节点和外部交互
    
    属性:
        host: 绑定IP
        port: 绑定port
        ResultThreads: 结果转发多线程
        ResultThreadsFlag:  结果转发多线程创建标志
    """
    def __init__(self,host,port):
        self.host = host
        self.port = port
        self.ResultThreadsFlag = 0



    def run(self):
        """
        服务器开始运行
        """
        print ("TaskServer on: {}:{}".format(self.host,str(self.port)))
        self.recv_short_conn(self.host, self.port)

    def MessageHandle(self, headPack, body, conn):
        """
        数据处理函数,子类可重构该函数
        """
        jdata = json.loads(body)
        print(type(jdata))
        print(jdata["key"])
        if headPack[0] == 1:
            if jdata["key"] == "startsystem":
                self.startsystem(jdata)

            elif jdata["key"] == "newtask":
                self.newtask(jdata)

            elif jdata["key"] == "pausetask":
                self.pausetask(jdata)

            elif jdata["key"] == "resumetask":
                self.resumetask(jdata)
                
            elif jdata["key"] == "shutdowntask":
                self.shutdowntask(jdata)

            elif jdata["key"] == "restart":
                self.restart(jdata)
            else:
                conn.send(str.encode("您输入的任务信息有误！"))
        else:
            conn.send(str.encode("暂未提供POST以外的接口"))


    def startsystem(self, jdata):
        """
        启动系统
        """
        try:
            DaspCommon.GUIinfo = jdata["GUIinfo"]
            self.sendRunDatatoGUI("接收任务请求")
        except KeyError:
            print ("非来自GUI的任务请求")

        name = "system"
        sdata = {
            "key": "startsystem",
            "GUIinfo": DaspCommon.GUIinfo
        }
        self.newtaskbase(name, sdata)

    def newtask(self, jdata): 
        """
        启动DAPP
        """
        name = jdata["DAPPname"]
        sdata = {
            "key": "newtask",
            "DAPPname": name
        }
        self.sendRunDatatoGUI("接收任务请求",name)
        self.newtaskbase(name, sdata)

    def newtaskbase(self, name, jdata): 
        """
        启动DAPP基本操作：加载任务、建立通信树、启动任务、启动数据转发线程
        """
        BaseServer.TaskDict[name] = Task(name)
        BaseServer.TaskDict[name].load()

        # 建立通信树
        sum = 0
        deleteID = []
        for ele in BaseServer.TaskDict[name].TaskIPlist:
            if ele:
                returnID = self.connect(ele[0], ele[1], ele[2], ele[3], ele[4], name)
                if returnID:
                    deleteID.append(returnID)
                else:
                    sum += 1
        for ele in deleteID:
            self.deleteadjID(ele)
            self.deleteTaskDictadjID(ele)
        if(sum == 0): BaseServer.TaskDict[name].treeFlag = 1   #只有一个节点的情况
        while (BaseServer.TaskDict[name].treeFlag == 0): {time.sleep(0.01)}
        self.sendRunDatatoGUI("通信树建立完成")

        #启动任务
        self.Forward2sonID(jdata,name)

        BaseServer.TaskDict[name].taskBeginFlag = 1
        self.sendFlagtoGUI(2,name)

        if self.ResultThreadsFlag == 0: #启动计算结果转发线程
            self.ResultThreads = threading.Thread(target=self.ResultForwarding,args=())
            self.ResultThreads.start()
            self.ResultThreadsFlag = 1

    def ResultForwarding(self):
        """
        根节点等待所有任务的数据收集结束标志，随后将计算结果转发到GUI界面
        """
        while 1:
            time.sleep(0.1)
            for key in BaseServer.TaskDict:
                if BaseServer.TaskDict[key].dataEndFlag == 1:
                    # time.sleep(1)   # 防止结果显示超前其他节点
                    BaseServer.TaskDict[key].sendDatatoGUI("任务数据收集完毕")
                    info = []
                    content = ""
                    Que = BaseServer.TaskDict[key].resultinfoQue
                    for i in range(len(Que)):
                        if Que[i]["info"]:
                            info.append({})
                            info[-1]["ID"] = Que[i]["id"]
                            info[-1]["value"] = str(Que[i]["info"]["value"])
                    
                    infojson = json.dumps(info, indent=2)  #格式化输出，更便于查看
                    content =  "Nodes name:{}\nInfo:{}\n\n".format(len(Que), infojson)
                    self.sendEndDatatoGUI(content,BaseServer.TaskDict[key].DAPPname)
                    self.sendFlagtoGUI(0,BaseServer.TaskDict[key].DAPPname)
                    BaseServer.TaskDict[key].taskEndFlag = 0
                    BaseServer.TaskDict[key].dataEndFlag = 0
                    BaseServer.TaskDict[key].resultinfoQue = []
                    BaseServer.TaskDict[key].resultinfo = {}

    def pausetask(self, jdata):
        """
        暂停DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].pause()
        self.sendFlagtoGUI(1,name)

    def resumetask(self, jdata):
        """
        恢复DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].resume()
        self.sendFlagtoGUI(2,name)

    def shutdowntask(self, jdata):
        """
        停止DAPP
        """
        name = jdata["DAPPname"]
        self.Forward2sonID(jdata,name)
        BaseServer.TaskDict[name].shutdown()
        self.sendFlagtoGUI(0,name)

    def restart(self, jdata):
        """
        将节点重连进分布式网络
        """
        try:
            DaspCommon.GUIinfo = jdata["GUIinfo"]
            self.sendRunDatatoGUI("重新连入系统")
        except KeyError:
            print ("非来自GUI的任务请求")

        name = "system"
        BaseServer.TaskDict[name] = Task(name)
        BaseServer.TaskDict[name].load()

        deleteID = []
        for ele in BaseServer.TaskDict[name].TaskIPlist:
            if ele:
                index = DaspCommon.adjID.index(ele[4])
                returnID = self.reconnect(ele[0], ele[1], ele[2], ele[3], ele[4], DaspCommon.adjDirectionOtherSide[index])
                if returnID:
                    deleteID.append(returnID)
        for ele in deleteID:
            self.deleteadjID(ele)
            self.deleteTaskDictadjID(ele)

        BaseServer.TaskDict[name].taskBeginFlag = 1
        self.sendFlagtoGUI(2,name)

        if self.ResultThreadsFlag == 0: #启动计算结果转发线程
            self.ResultThreads = threading.Thread(target=self.ResultForwarding,args=())
            self.ResultThreads.start()
            self.ResultThreadsFlag = 1

class CommServer(BaseServer):
    """
    通信服务器，用于节点和其他节点通信
    """
    host = "locolhost"
    port = 10000

    def __init__(self,host,port):
        self.host = host
        self.port = port

    def run(self):
        """
        服务器开始运行
        """
        print ("CommServer on: {}:{}".format(self.host,str(self.port)))
        self.recv_long_conn(self.host, self.port)

    def MessageHandle(self, headPack, body, conn):
        """
        数据处理函数
        """
        jdata = json.loads(body)
        if headPack[0] == 1:
            #建立通信树
            if jdata["key"] == "connect":
                self.RespondConnect(conn, jdata)

            elif jdata["key"] == "OK":
                self.RespondOK(jdata)

            elif jdata["key"] == "startsystem":
                self.RespondStartSystem(jdata)

            elif jdata["key"] == "newtask":
                self.RespondNewTask(jdata)

            elif jdata["key"] == "shutdowntask":
                self.RespondShutDownTask(jdata)

            elif jdata["key"] == "pausetask":
                self.RespondPauseTask(jdata)
            
            elif jdata["key"] == "resumetask":
                self.RespondResumeTask(jdata)

            elif jdata["key"] == "data":
                self.RespondData(jdata)

            elif jdata["key"] == "questionData":
                self.RespondQuestionData(jdata)
                
            elif jdata["key"] == "sync":
                self.RespondSync(jdata,1)

            elif jdata["key"] == "sync2":
                self.RespondSync(jdata,2)

            elif jdata["key"] == "reconnect":
                self.RespondReconnect(conn, jdata)

            else:
                conn.send(str.encode("请不要直接访问通信服务器"))
        else:
            print("非POST方法")
            conn.send(str.encode("请不要直接访问通信服务器"))


    def RespondConnect(self, conn, jdata):
        """
        回应连接请求
        如果在通信树中则发送回已连接消息
        如果不在通信树中则新建一个Task实例并加入通信树，并转发连接请求
        加入通信树后如果是叶子节点向父节点发送OK信号
        """
        name = jdata["DAPPname"]
        # 如果当前节点已经在通信树中，则发回connect消息
        if name in BaseServer.TaskDict:
            if BaseServer.TaskDict[name].commTreeFlag == 1:
                data = {
                    "key": "connected",
                    "host": self.host,
                    "port": self.port,
                    "id": DaspCommon.nodeID,
                    "DAPPname": name
                }
                self.sendall_length(conn, data)
                return 0

        # 如果当前节点不在通信树中，则加入通信树
        BaseServer.TaskDict[name] = Task(name)
        BaseServer.TaskDict[name].load()
        BaseServer.TaskDict[name].parentID = jdata["id"]
        indext = DaspCommon.adjID .index(jdata["id"])
        BaseServer.TaskDict[name].parentDirection = DaspCommon.adjDirection[indext]
        print ("connected to {}:{} ".format(jdata["host"],jdata["port"]))
        DaspCommon.GUIinfo = jdata["GUIinfo"]
        data = {
            "key": "connect",
            "host": self.host,
            "port": self.port,
            "id": DaspCommon.nodeID,
            "GUIinfo": DaspCommon.GUIinfo,
            "DAPPname": name
        }
        self.sendall_length(conn, data)
        
        deleteID = []
        for ele in BaseServer.TaskDict[name].TaskIPlist:
            if ele != []:
                # if ele[4] != BaseServer.TaskDict[name].parentID:
                returnID = self.connect(ele[0], ele[1], ele[2], ele[3], ele[4], name)
                if returnID:
                    deleteID.append(returnID)

        for ele in deleteID:
            self.deleteadjID(ele)
            self.deleteTaskDictadjID(ele)

        #如果是叶子结点
        if len(BaseServer.TaskDict[name].sonID) == 0:
            data = {
                "key": "OK",
                "id": DaspCommon.nodeID,
                "DAPPname": name
            }
            ndata = json.dumps(data)
            self.send(BaseServer.TaskDict[name].parentID, data=ndata)
            for i in range(len(BaseServer.TaskDict[name].CreateTreeSonFlag)):
                BaseServer.TaskDict[name].CreateTreeSonFlag[i] = 0

    def RespondReconnect(self, conn, jdata):
        """
        回应节点重新连接请求
        如果申请方向未被占用，则将该节点加入子节点中
        """
        if jdata["applydirection"] not in DaspCommon.adjDirection:

            direction = jdata["applydirection"] - 1

            tempiplist = []
            tempiplist.append(self.IP)
            tempiplist.append(self.PORT[direction])
            tempiplist.append(jdata["host"])
            tempiplist.append(jdata["port"])
            tempiplist.append(jdata["id"])

            DaspCommon.IPlist.append(tempiplist)
            DaspCommon.adjID.append(jdata["id"])
            DaspCommon.adjDirection.append(jdata["applydirection"])

            BaseServer.TaskDict["system"].sonDirection.append(jdata["applydirection"])
            BaseServer.TaskDict["system"].sonID.append(jdata["id"])
            BaseServer.TaskDict["system"].CreateTreeSonFlag.append(0)
            BaseServer.TaskDict["system"].sonData.append([])
            BaseServer.TaskDict["system"].TaskIPlist.append(tempiplist)
            BaseServer.TaskDict["system"].TaskadjID.append(jdata["id"])
            BaseServer.TaskDict["system"].TaskadjDirection.append(jdata["applydirection"])
            BaseServer.TaskDict["system"].adjSyncStatus.append([]) 
            BaseServer.TaskDict["system"].adjSyncStatus2.append([]) 
            BaseServer.TaskDict["system"].adjData.append([]) 
            BaseServer.TaskDict["system"].adjData_another.append([]) 
            self.sendRunDatatoGUI("与邻居节点{0}重连成功，已添加和{0}的连接".format(jdata["id"])) 
        else:
            conn.send(str.encode(head + "节点{}方向{}已被占用，请选择其他方向！".format(DaspCommon.nodeID,str(jdata["applydirection"]))))

    def RespondOK(self, jdata):
        """
        回应OK信号，如果所有子节点都OK则向父节点发送OK信号
        如果自己是根节点则通信树建立完毕
        """
        name = jdata["DAPPname"]
        data = {
            "key": "OK",
            "id": DaspCommon.nodeID,
            "DAPPname": name
        }
        ndata = json.dumps(data)
        for i in range(len(BaseServer.TaskDict[name].sonID)):
            if BaseServer.TaskDict[name].sonID[i] == jdata["id"]:
                BaseServer.TaskDict[name].CreateTreeSonFlag[i] = 1

        if all(BaseServer.TaskDict[name].CreateTreeSonFlag):
            if BaseServer.TaskDict[name].parentID != DaspCommon.nodeID:
                self.send(BaseServer.TaskDict[name].parentID, data=ndata)
            else:
                BaseServer.TaskDict[name].treeFlag = 1
                print ("The communication tree has been constructed!")
            for i in range(len(BaseServer.TaskDict[name].CreateTreeSonFlag)):
                BaseServer.TaskDict[name].CreateTreeSonFlag[i] = 0

    def RespondStartSystem(self, jdata):
        """
        回应启动系统信号，广播子节点启动系统信号，启动系统DAPP
        """
        self.Forward2sonID(jdata, "system")
        BaseServer.TaskDict["system"].taskBeginFlag = 1

    def RespondNewTask(self, jdata):
        """
        回应新任务信号，广播子节点启动任务信号，启动任务DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].taskBeginFlag = 1

    def RespondPauseTask(self, jdata):
        """
        回应暂停任务信号，广播子节点暂停任务信号，暂停任务DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].pause()

    def RespondResumeTask(self, jdata):
        """
        回应恢复任务信号，广播子节点恢复任务信号，恢复任务DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].resume()

    def RespondShutDownTask(self, jdata):
        """
        回应结束任务信号，广播子节点结束任务信号，结束任务DAPP
        """
        name = (jdata["DAPPname"])
        self.Forward2sonID(jdata, name)
        BaseServer.TaskDict[name].shutdown()

    def RespondData(self, jdata):
        """
        回应子节点任务结束信号，并收集数据
        """
        name = jdata["DAPPname"]
        index = BaseServer.TaskDict[name].sonID.index(jdata["id"])
        BaseServer.TaskDict[name].sonData[index] = jdata["data"]
        if all(BaseServer.TaskDict[name].sonData):
            BaseServer.TaskDict[name].sonDataEndFlag = 1

    def RespondQuestionData(self, jdata):
        """
        回应任务发送数据信号，并存储数据
        """
        name = jdata["DAPPname"]
        index = BaseServer.TaskDict[name].TaskadjID.index(jdata["id"])
        if jdata["type"] == "value":
            BaseServer.TaskDict[name].adjData[index] = jdata["data"]

        elif jdata["type"] == "value2":
            BaseServer.TaskDict[name].adjData_another[index] = jdata["data"]

    def RespondSync(self, jdata, type):
        """
        回应同步请求，并改变相应标志位
        """
        name = jdata["DAPPname"]
        index = BaseServer.TaskDict[name].TaskadjID.index(jdata["id"])
        if type == 1:
            BaseServer.TaskDict[name].adjSyncStatus[index] = 1
        else:
            BaseServer.TaskDict[name].adjSyncStatus2[index] = 1

if __name__ == '__main__':

    DaspCommon.GUIinfo = ["172.23.96.1", 50000]
    DaspCommon.nodeID = "room_2"
    task = Task("debugDAPP")
    task.load()
    BaseServer.TaskDict["debugDAPP"] = task
    BaseServer.TaskDict["debugDAPP"].taskBeginFlag = 1