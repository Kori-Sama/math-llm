# 目的

COT模型复现了论文https://arxiv.org/pdf/2210.03493，实现了思维链

TIR模型实现了python解释器的调用（模型处理），PlantUML代码转为图(前端处理)

# 输入

```
{
	query:str, #⽤⼾提出的问题
	history_chat:List[str] #历史对话数据。即在这个uid和cid下，能在数据库找的所有对话数据。格式应该为[Q1,A1,Q2,A2，...]。如果本次对话为新的对话，即忘记记忆或者新⽤⼾的第⼀段对话。返回空List，即[]。
8 }
```

# 输出

sse协议，流式输出

```
data:{
	status:int,
	error:str,
	answer:str
}\n\n
```

status为状态，小于0为不正常情况，错误在error中显示。

# 注意

COT模型是纯markdown格式

TIR是markdown中加入了

```
<Python></Python>
```

```
<PlantUML></PlantUML>
```

包裹对应代码

模型正常返回时，status为0

当输出的是python代码执行的结果时，status为1

PlantUML代码转为图这个步骤稍微会麻烦一些。测试数据可以参考群里的output.csv文件。其中中，第四列有1标签的数据，表示数据含有PlantUML代码



