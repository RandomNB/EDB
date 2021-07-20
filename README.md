# EDB 以太坊单合约交易调试工具

### Idea

在刷题的时候遇到一类```JOP```(Jump-Oriented-Programming)的题目，fuzz或者调试这类题目缺少简单易用的工具，由此开发了一个简单的调试工具```EDB```(The Ethereum Debugger)，利用```debug_traceTransaction```的rpc调用实现调用复现，目前仅支持单合约调试，由于关闭了Memory下载，因此大部分情况下不会出现geth崩溃的问题（参考QWB2020线下赛EthGaMe），Memory采用手动模拟实现，缺点是跨合约指令较为繁琐，目前没有精力全部模拟，只支持单合约交易的调试

### 环境要求

1. python >= 3.6
2. 开启```debug_traceTransaction```RPC调用的以太坊网络，推荐[ganache](https://github.com/trufflesuite/ganache-cli)
3. pip install -r requirements.txt
4. Windows平台没有经过测试，建议在Linux和macOS系统使用


### 说明

1. 修改```config.py```中的```ENDPOINT_URI```
2. 执行```python edb.py TXHASH```

### 调试命令

1. ```n [delta]```: 执行下一条或下delta条指令，可以为负数
2. ```r```: 顺序执行直到下一个断点或结束
3. ```rb```: 逆序执行直到上一个断点或起始
4. ```b op=sha3;sta[-2]=0x100```: 下条件断点，可用条件如下：
        a. op: 操作码
        b. sta[xx]: 栈元素
        c. sto[xx]: storage元素
        d. pc: pc指针
5. ```p mem|sto|sta```: 打印全部Memory或Storage或Stack，限制大小可以在```config.py```中修改
6. ```x mem[a:b]|sto[k]|sta[k]```: 打印Memory或Storage或Stack上特定位置的数值
7. ```db i```: 删除第i个断点
8. ```g step```: 跳转到step位置
9. ```j```: 打印当前跳转栈
10. ```ws k```: 向后执行直到stack[k]的元素发生变化，用于追踪栈上元素来源
11. ```q```: 退出