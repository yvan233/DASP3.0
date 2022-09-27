# 无根节点的生成树 生成和维护
# 测试节点3的在系统启动后加入
from DASP.module import Task
import time
def drc2id(adjDirection,adjID,drc):
    return adjID[adjDirection.index(drc)]
            
def taskFunction(self:Task,id,adjDirection:list,datalist):
    adjID = self.TaskadjID 
    flag = False 
    parent = -1
    child = []    
    edges = [False] * len(adjDirection)
    min_uid = id
    flag = True
    step = 1

    test_id = ""
    testflag = 1 

    # 测试修改拓扑
    if id in ["room_2","room_6","pump_1"]:
        test_id = "room_3"
        index = index = adjID.index(test_id)
        del adjID[index]
        del adjDirection[index]   
        del edges[index]
        test_id = ""


    if id == "room_3":
        time.sleep(10)

    for ele in adjDirection:
        self.sendAsynchData(ele,["search",id])
    j,(data,token) = self.getAsynchData()
    while True:
        if step == 1:
            while True:
                if token <= min_uid:
                    if token < min_uid:
                        min_uid = token
                        flag = False
                        parent = -1
                        child = []
                        edges = [False] * len(adjDirection)

                    edges[adjDirection.index(j)] = True
                    if data == "end":
                        if j == parent:
                            for ele in child:
                                self.sendAsynchData(ele,["end",min_uid]) 
                            break

                    # 如果邻居传来join信号
                    elif data == "join":
                        if j not in child:
                            child.append(j)
                    # search
                    else:
                        if flag == False:
                            flag = True
                            parent = j  #将邻居方向加入父节点方向
                            # 向其他邻居广播BFS信号
                            for ele in adjDirection:
                                if ele != j:
                                    self.sendAsynchData(ele,["search",min_uid])
                                    
                    if all(edges):
                        if min_uid == id:
                            leader_state = "leader"
                            for ele in child:
                                self.sendAsynchData(ele,["end",min_uid]) 
                            break
                        else:
                            leader_state = "non-leader"  
                            self.sendAsynchData(parent,["join",min_uid]) 
                j,(data,token) = self.getAsynchData()
                self.sendDatatoGUI("recv from {}:[{},{}]".format(j,data,token))
                            

            child_show = [drc2id(adjDirection,adjID,ele) for ele in child]
            parent_show = [drc2id(adjDirection,adjID,parent) if parent != -1 else -1]
            value = {"parent":parent_show,"child":child_show}
            self.sendDatatoGUI(f"{value}")
            step = 2

        if id in ["room_2","room_6","pump_1"]:
            if testflag == 1: 
                adjID.append("room_3")
                adjDirection.append(5) 
                edges.append(False)
                testflag = 0
                
        if step == 2:
            if test_id:
                index = adjID.index(test_id)
                if adjDirection[index] == parent:
                    del adjID[index]
                    del adjDirection[index]   
                    del edges[index]

                    flag = False 
                    parent = -1
                    child = []    
                    edges = [False] * len(adjDirection)
                    min_uid = id
                    flag = True
                    step = 1
                    for ele in adjDirection:
                        self.sendAsynchData(ele,["search",min_uid])
                    self.sendDatatoGUI(f"已删除和{test_id}的链接")
                    j,(data,token) = self.getAsynchData()
                    self.sendDatatoGUI("recv from {}:[{},{}]".format(j,data,token))
                    test_id = ""
                    continue

                elif adjDirection[index] in child:
                    child.remove(adjDirection[index])
                    del adjID[index]
                    del adjDirection[index]   
                    del edges[index]
                    test_id = ""
                    self.sendDatatoGUI(f"已删除和{test_id}的链接")
                else:
                    del adjID[index]
                    del adjDirection[index]   
                    del edges[index]
                    test_id = ""
                    self.sendDatatoGUI(f"已删除和{test_id}的链接")
            else:
                j,(data,token) = self.getAsynchData()
                self.sendDatatoGUI("recv from {}:[{},{}]".format(j,data,token))
                
                if j == parent:
                    parent = -1
                    child = []    
                    edges = [False] * len(adjDirection)
                    min_uid = id
                    flag = True
                    step = 1
                    if min_uid < token:
                        for ele in adjDirection:
                            self.sendAsynchData(ele,["search",id])
                else:
                    if j in child:
                        child.remove(j)
                    edges[adjDirection.index(j)] = False
                    
                    if token > min_uid:
                        self.sendAsynchData(j,["search",min_uid]) 
                    elif token < min_uid:
                        step = 1
                    else:
                        edges[adjDirection.index(j)] = True
                        if data == "join":
                            child.append(j)
                            self.sendAsynchData(j,["end",min_uid]) 
                        elif data == "search":
                            self.sendAsynchData(j,["end",min_uid]) 


    child = [drc2id(adjDirection,adjID,ele) for ele in child]
    parent = [drc2id(adjDirection,adjID,ele) for ele in parent if ele != -1]
    value = {"state":leader_state,"parent":parent,"child":child}

    return value