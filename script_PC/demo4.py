# 测试节点一个个启动，逐步接入网络
import time 
import sys
sys.path.insert(1,".")
from DASP.module import Node,Moniter
from DASP.control import ControlMixin


nodelist = []
Controlmixin = ControlMixin("Pc")

# 启动监控脚本
moniter = Moniter()
moniter.run()

node = Node(0)
nodelist.append(node)
print("启动系统")

time.sleep(15)
print("启动room_2")
node = Node(1)
nodelist.append(node)

time.sleep(15)
print("启动room_3")
node = Node(3)
nodelist.append(node)

moniter.wait()