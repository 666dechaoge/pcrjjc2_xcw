# pcrjjc2_xcw

基于[pcrjjc2](https://github.com/cc004/pcrjjc2)公版，参考[pcrjjc_huannai](https://github.com/SonderXiaoming/pcrjjc_huannai/)魔改，适配2022/05/08之后使用async chara icon的Hoshino版本，未经大量测试，如有问题请换回公版

## 魔改特点

1. 可以添加多个pcr账号模拟多个客户端查询，支持查询各个客户端可用性状态
2. 订阅与历史记录均使用sqlite存储，单用户可以绑定多个订阅（默认限制最多三个）
3. 支持新版自动过验证码（感谢大佬们提供的过码服务）兼容手动过验证码
4. 登录提醒以及指定排名以内提醒
5. 查询具体群订阅，对失效群聊以及非活跃订阅进行清理

可选功能

6. 击剑风控，每15分钟检查变化超过5次的用户将自动被关闭订阅，下次检查正常则自动恢复，避免刷屏，可关闭
7. 状态通知，当推送服务不可用或者服务恢复的时候是否通知以及通知方式
8. 同群订阅分享，可@群友查询群友订阅信息，关闭后则只能查询自己

## 配置方法

1.下载release的压缩包并按照说明放在指定文件夹

2.更改account.json内的account和password为bilibili账号的用户名和密码（仅1个账号也可），管理账号与接收验证码的人员取自bot的主人。 

3.服务默认不启用，要为需要服务的群聊手动开启

4.(可选)配置插件自带的验证码网页，不配置只使用公共的也可以

- 有公网IP情况下以下三种方法任选一种即可，需要修改机器人的配置文件__bot__.py

(1)添加PUBLIC_ADDRESS属性，适用于已经对访问bot做了自定义的情况，示例：

```python
PUBLIC_ADDRESS = 'example.com:8080'  # 设置能访问到bot的域名，域名端口或者IP端口组合
```
(2)添加IP属性，搭配端口使用，需要HOST设置为'0.0.0.0'，并开放bot的端口,将bot暴露在公网上⚠，强烈推荐配置好ACCESS_TOKEN再使用，示例：

```python
HOST = '0.0.0.0'  # 开放公网访问使用此条配置（不安全）
PORT = 8080
IP = '1.1.1.1' # bot公网IP
ACCESS_TOKEN: '' # 需要和gocqhttp配置的access-token相同
```

(3)自动访问4.ipw.cn获取公网IP，搭配端口使用，需要HOST设置为'0.0.0.0'，并开放bot的端口,将bot暴露在公网上⚠，强烈推荐配置好ACCESS_TOKEN再使用，示例：

```python
HOST = '0.0.0.0'  # 开放公网访问使用此条配置（不安全）
PORT = 8080
ACCESS_TOKEN: '' # 需要和gocqhttp配置的access-token相同
```

- 没有公网IP，请直接在bot运行的计算机上使用localhost+端口来访问

5.(可选)用户订阅改用sqlite存储，可将目录下的jjcconvert.back改为jjcconvert.py，与binds.json放在同一目录下执行，尝试将公版json绑定信息导入到数据库。

## 使用指令

### 普通用户

#### 订阅添加与查询

| 关键词        | 说明                              |
|------------|---------------------------------|
| 竞技场绑定 id   | 绑定竞技场排名变动推送，默认双场均启用，仅排名降低时，全天推送 |
| 竞技场查询      | 查询竞技场简要信息                       |
| 查询竞技场列表    | 查询绑定的订阅信息，按序号依次排列               |
| 竞技场历史      | 查询战斗竞技场变化记录（战斗竞技场订阅开启有效，可保留10条） |
| 公主竞技场历史    | 查询公主竞技场变化记录（公主竞技场订阅开启有效，可保留10条） |
| 详细竞技场查询 id | 查询账号详细信息                        |

#### 订阅修改与删除

##### 基本

**以下命令除最后一项外需要先发送【选择竞技场订阅+序号】后才可使用**

| 关键词       | 说明                    |
|:----------|:----------------------|
| 停止竞技场订阅   | 停止战斗竞技场排名变动推送         |
| 停止公主竞技场订阅 | 停止公主竞技场排名变动推送         |
| 启用竞技场订阅   | 启用战斗竞技场排名变动推送         |
| 启用公主竞技场订阅 | 启用公主竞技场排名变动推送         |
| 切换群聊      | 排名变化信息发送到群            |
| 切换私聊      | 排名变化信息私聊发送(需要为bot的好友) |
| 删除竞技场订阅   | 删除选择的竞技场订阅            |
| 清空我的竞技场订阅 | 清空该用户的订阅              |

##### 进阶

**以下命令需要先发送【选择竞技场订阅+序号】后才可使用**

| 关键词       | 说明                                    |
|:----------|:--------------------------------------|
| 仅下降开/关    | 开:仅推送排名下降信息 关:推送全部                    |
| 全天开/关     | 开:全天推送排名变化信息 关:每天13:00-16:00间推送排名变化信息 |
| 登录提醒开/关   | 开启则推送绑定账号最新在线时间,默认30分钟以上才会推送          |
| 提醒间隔num分钟 | 设置登录提醒的忽略间隔时间                         |
| 提醒排名num名  | 设置在指定排名以内提醒                           |

### 管理员

#### 客户端管理

**以下命令需要bot的主人私聊bot触发，其中序号为pcrstatus查询到的客户端序号**

| 关键词           | 说明                               |
|:--------------|:---------------------------------|
| pcrstatus     | 查询各个客户端可用性状态                     |
| pcrstatus 序号  | 查询具体客户端状态（空格必须）                  |
| pcrval 序号 验证码 | 按需手动过客户端验证码 （空格必须）               |
| pcrlogin 序号   | 客户端连续5次出错会自锁，需要手动解除锁定来继续尝试（空格必须） |

#### jjc功能设置

##### jjc设置

**以下命令需要bot的主人才能触发**

| 关键词           | 说明            |
|:--------------|:--------------|
| jjc设置 设置项 设置值 | 设置可选功能 （空格必须） |
| jjc设置状态       | 查询设置状态        |

##### 设置项以及设置值
| 设置项          | 设置值                          | 作用                                                 |
|:-------------|:-----------------------------|:---------------------------------------------------|
| 击剑风控(detect) | 开启/on(默认) 关闭/off             | 开启后，每15分钟检查变化超过5次的用户将自动被关闭订阅，下次检查正常则自动恢复,一定程度上避免刷屏 |
| 状态通知(notify) | 主人/admin(默认) 广播/broad 关闭/off | 当推送服务不可用或者服务恢复正常时候，是否通知以及通知方式，广播会通知所有启用服务的群聊       |
| 绑定数(limit)   | 具体数值(默认为3)                   | 单个用户最大绑定数量                                         |
| 订阅分享(share)  | 开启/on(默认) 关闭/off             | 开启后，可@群友查询群友订阅信息，关闭则只能查询自己的订阅信息                    |

示例1: jjc设置 击剑风控 关闭

示例2：jjcset notify broad

#### 订阅统计与管理

**以下命令需要bot的主人才能触发**

| 关键词        | 说明                                                        |
|:-----------|:----------------------------------------------------------|
| jjc状态查询    | 查询bot所在群的服务状态                                             |
| jjc群查询     | 查询启用服务的群用户以及订阅数                                           |
| jjc用户查询 群号 | 查询具体群内用户以及订阅数（空格必须）                                       |
| jjc无效清理    | 手动清理已经关闭服务的群以及bot已经不在群的订阅信息                               |
| jjc睡眠清理 排名 | 手动清理双场均在指定排名(输入大于50的数字，保证至少保留双场排名还在50以内的订阅)的非活跃订阅信息（空格必须） |
| jjc风控列表    | 查看被击剑风控临时关闭的订阅信息                                          |

## TODO
web管理订阅
