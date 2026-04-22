---
title: SSH 端口转发
date: 2026-04-22 15:02:09
tags:
- 网络
- ssh
categories:
- 技术
abbrlink: 39bfc8ae
---

## SSH 端口转发和会话连接

有时候连 ssh 需要过几次跳板机。可以通过多个 ssh 隧道转发实现直连，只需要敲一次 ssh 命令。

这里的示例是反向能直连的情况，不能直连需要在跳板机上也搭好隧道。

### 参数

```
ssh -NT -R 8080:localhost:3000 user@server
```

| 参数 | 含义                 | 为什么常用                     |
| :--- | :------------------- | :----------------------------- |
| `-N` | **不执行远程命令**   | 只做端口转发，不需要登录 shell |
| `-T` | **禁用伪终端分配**   | 节省资源，避免分配不必要的 TTY |
| `-R` | **在远端开监听端口** | 让远端访问本地服务             |
| `-L` | **在本地开监听端口** | 让本地访问远端服务             |

**远端指被连接者，本地指连接者。**

### 输入

`8080:localhost:3000`：`[listen host]:{listen port}:{target host}:{target port}` 

- `[listen host]`：可选，默认 `127.0.0.1`，控制能到连接到的监听端口的来源主机，默认只允许**监听侧的本机**。

  - `-R` 的情况下，**该参数默认不生效**，想让该参数生效，必须要**远端**改 `GatewayPorts` 允许任意远端侧来源的流量。需要尊重远端的配置

- `{listen port}`：必须，指定监听端口号

- `{target host}`：必须，指定把监听端口数据包送到哪个主机去，`{target host}` 是一个**相对位置**，如果 `-R`，那么就是相对本地的，如果是 `-L` 就是相对远端的。

- `{target port}`：必须，送到主机的哪个端口。

  **两侧本来是独立的**，通过隧道可以关联起来，**关联的是两个局域网，不是单纯的两个机器**。

  更具体的，执行 `ssh -L` 命令后，对于任意机器，访问**监听侧等效于访问目标侧**，这个等效是**双工**的，目标侧可以收到访问侧的数据包，访问侧也能接收到目标侧的的数据包。

  例如 `ssh -NT -R 8080:localhost:3000 user@server` 后，在远端访问 `localhost:8080`，就等效于和本地的 `localhost:3000` 交互。

## 会话连接

### 会话创建

在 ssh 连接中产生的进程会归属到 ssh **会话**。

ssh 连接时，自动启动一个新的会话，将 `shell` 设置为**前台进程组**，sshd 守护进程是会话的首进程。

### 会话断开

ssh 断开后，系统会主动向整个**会话**发送 `SIGHUP`，会话首进通常会随信号终止，`SIGHUP` 会进一步送到**会话内的所有进程**。

大部分程序没有定义处理 `SIGHUP` 的部分，**默认终止**。

用 `&` 扔给后台没用，因为信号同时发送到所属会话的**全部进程组**。

### 后台运行方案

- `nohup` 前缀运行，默认忽略 `SIGHUP`，比如 `nohub sh xxx.sh`，最轻量。
- `disown`：解除任务和当前进程的关联。
- `setsid`：创建新会话运行。
- `screen/tmux`：完整会话管理

## 自动重连

安装 autossh 使用即可，外面套了一个自动重试重连。

默认是基于心跳包的重连机制，默认心跳包是 10min，一般会显式设置为 30s 或者更短

```bash
autossh -M 0 \
    -v \
    -o "ServerAliveInterval 30" \
    -o "ServerAliveCountMax 3" \
    -o "ExitOnForwardFailure=yes" \
    -o "ConnectTimeout=10" \
    -NT \
    -R 2222:localhost:22 \
    user@server
```

## VSCode 端口转发

- 本质是 `ssh -L xxxx:127.0.0.1:yyyy user@server`。

## 重定向和合并符号

`>`：覆盖写入，前面的参数可以缺省，默认为 stdout。

`>>`：追加写入，前面的参数可以缺省，默认为 stdout。

`2>&1`：专有语法，把文件描述符 2 （stderr）的输出位置**指向**文件描述符 1（stdout）

### 常用组合

`nohup my_command > output.log 2>&1 &`：注意顺序，必须先把 stdout 指向文件，**再把 stderr 指向 stdout 所指的内容**。

## 相关命令

```bash
ssh-keygen -t ed25519 -C "youremail@example.com"
```
