---
title: 使用 Linux 服务运行程序
date: 2026-04-22 14:40:26
tags:
  - 服务
  - Linux
categories:
  - 技术
abbrlink: cfdf3e2b
---

# 使用 Linux 服务运行程序

在 ssh 终端中运行的程序和 ssh 会话生命周期绑定，**会话断开程序就会被杀**。

使用 tmux、screen 当然可以解决进程和会话绑定的问题，但解决不了开机自启等问题，而且比较重。

对于需要持续稳定运行的进程，使用**服务**功能是更专业和便捷的方案。

不过，由于 Docker 普通容器启动模式的问题，**Docker** 中无法使用服务功能。

## systemd 服务

### 配置文件

命名为 `xxx.service`，后缀名 `.service` 是**必须**的。

文件放在 `/etc/systemd/system` 目录下。

可以使用 `#` 来写注释，参考如下：

```bash
[Unit] # 定义服务元信息和依赖关系
Description=服务描述
After=network.target
Requires=network.target mysql.service
RequiresMountsFor=/path

[Service]
User=myuser # 默认 root 可以缺省
WorkingDirectory=/opt/myapp # 工作目录，缺省默认 /
ExecStart=/usr/bin/python3 /opt/myapp/myapp.py # 实际执行的命令
Restart=on-failure # 默认 no
RestartSec=5s # 可以缺省

[Install]
WantedBy=default.target
```

#### Unit

After 和 Requires 独立是为了考虑以下情况：

- XXX 不依赖 YYY，但是为了**避免资源竞争**，所以只需要 XXX 在 YYY 后面启动（只写 After）
- XXX 依赖 YYY（After 和 Requires 都要写）

用**空格隔开不同的服务**以声明多个依赖（注意自定义服务需要写 `.service` 后缀）

RequiresMountsFor 用来**显式要求**某些路径已经挂载好，通常来讲，如果只需要用 `/var`，`/opt`，`/ect`，`/tmp` 等常规目录，那么可**以不用声明路径挂载依赖**。

*系统会隐式添加一些基础的依赖。*

#### Service

User：执行的用户，默认 root。

Restart：控制重启策略，重启默认有 5s/100ms 等限流。

- `no`：默认，不重启。
- `on-failure`：失败退出时重启，包括非零退出，被信号终止，超时等，**最常用**。

#### Install

WantedBy 参数用于控制 enable 的语义，一般写 `default.target`。这样在执行 `systemctl enable xxx.service` 时，可以将**服务加入开机自启**的队列。

### 管理命令

一般用 sudo 执行，例如 ：

`````bash
sudo systemctl start xxx.service
`````

如果是 `xxx.service`，后缀可以**省略**，直接：

 ```bash
sudo systemctl start xxx
 ```

针对服务常见命令有：

- start、stop、status、restart。

- enable、disable：用于控制服务**开机自启**。
- reload：重载服务配置，需要服务声明 `ExecReload` 支持热重载。

针对 systemd 本身常见命令有：

- daemon-reload：常用于让 systemd 扫描**服务配置文件的变化**。

*ctl 是 control 的简写。*

## journal 日志

`journald` 是 Systemd 自带的日志收集系统，而 `journalctl` 则是专门用来**查询和查看**这些日志的强大命令行工具。

### 持久化日志目录

默认情况下，journal 日志写到 `/run/log/journal`，机器重启后会丢失。

如果希望不丢失，需要创建 `/var/log/journal`，只要有这个文件，就能**自动写到这里**，不丢失。

如果刚刚创建目录，需要重启 `systemd-journald` 让配置生效。

### 常用命令

`journalctl`：查看所有日志。

`journalctl -u <服务名>` 查看指定服务的日志。

`journalctl -f` 动态显示新的日志。

`journalctl --since "时间" --until "时间"`：按照时间过滤日志。

可以组合使用

## 一些常识

### 各个目录用途

#### opt

- 存放**第三方、手动安装的、自包含的**大型软件包。通常每个软件放在自己的子目录中（如 `/opt/nginx`、`/opt/teams`）。
- **特点**：软件**自身包含所有依赖、配置文件、可执行文件**等，**不分散**到 `/usr` 或 `/etc` 中。卸载时直接移除目录就卸载干净了。
- **与服务相关**：自定义服务如果安装到 `/opt/myapp`，对应的 `.service` 文件通常仍放在 `/etc/systemd/system/`，而服务程序本身位于 `/opt/myapp/bin/`。

#### etc

- **用途**：存放**系统级配置文件**（文本格式，通常为 `.conf`、`.ini`、`.yaml` 等）。
- **特点**：所有软件的全局配置几乎都位于此目录或其子目录中。例如：
  - `/etc/nginx/nginx.conf`
  - `/etc/systemd/system/`（自定义服务单元文件）
  - `/etc/hosts`、`/etc/fstab`

*同一软件视安装方式的不同可以有不同的组织策略，如果 nginx 是用 apt 安装的，那么默认情况下，把配置文件放到 `/etc`，把可执行文件放到 `/usr` 是合理的。如果手动安装，全部放到 `/opt` 就是正确的*。

#### run

- **用途**：存放**系统启动以来产生的、易失的运行时数据**，如进程 PID 文件、套接字文件、系统状态信息。
- **特点**：**tmpfs**（内存文件系统），重启后清空。

#### var

- **用途**：存放**预期会持续增长或变化的数据**，如日志、缓存、假脱机文件、临时文件（但重启后通常保留）。
- **子目录**：`/var/log/` 、`/var/cache/`、`/var/tmp`

*`/opt` 下的软件，日志也推荐打到 `/var`*

#### usr

- **用途**：**系统范围的只读程序和数据**（用户软件资源）。大部分软件默认安装在此，如 `/usr/bin`、`/usr/lib`、`/usr/share`。