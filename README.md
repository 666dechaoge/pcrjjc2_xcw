# pcrjjc2_xcw

基于[pcrjjc2](https://github.com/cc004/pcrjjc2)公版，参考[pcrjjc_huannai](https://github.com/SonderXiaoming/pcrjjc_huannai/)魔改，未经大量测试，如有问题请换回公版

## 魔改特点

1. 可以添加多个pcr账号模拟多个客户端查询，支持查询各个客户端可用性状态
2. 订阅与历史记录均使用sqlite存储，单用户可以绑定多个订阅（限制最多三个）
3. 自动过验证码(同样感谢lulu大佬自动过验证的服务器)，如出现问题也可手动过验证

## 配置方法

下载release的压缩包并按照说明放在指定文件夹，更改account.json内的account和password为bilibili账号的用户名和密码（仅1个账号也可），管理账号与接收验证码的人员取自bot的主人。 

魔改版本用户订阅使用sqlite存储，可将目录下的jjcconvert.back改为jjcconvert.py执行，尝试将公版json绑定信息导入。

## 订阅指令

### 订阅添加与查询

| 关键词        | 说明                              |
|------------|---------------------------------|
| 竞技场绑定 id   | 绑定竞技场排名变动推送，默认双场均启用，仅排名降低时，全天推送 |
| 竞技场查询      | 查询竞技场简要信息                       |
| 查询竞技场列表    | 查询绑定的订阅信息，按序号依次排列               |
| 竞技场历史      | 查询战斗竞技场变化记录（战斗竞技场订阅开启有效，可保留10条） |
| 公主竞技场历史    | 查询公主竞技场变化记录（公主竞技场订阅开启有效，可保留10条） |
| 详细竞技场查询 id | 查询账号详细信息                        |

### 订阅修改与删除

#### 基本

**以下命令需要先发送【选择竞技场订阅+序号】后才可使用**

| 关键词       | 说明                    |
|:----------|:----------------------|
| 停止竞技场订阅   | 停止战斗竞技场排名变动推送         |
| 停止公主竞技场订阅 | 停止公主竞技场排名变动推送         |
| 启用竞技场订阅   | 启用战斗竞技场排名变动推送         |
| 启用公主竞技场订阅 | 启用公主竞技场排名变动推送         |
| 切换群聊      | 排名变化信息发送到群            |
| 切换私聊      | 排名变化信息私聊发送(需要为bot的好友) |
| 删除竞技场订阅   | 删除选择的竞技场订阅            |

#### 扩展

**以下命令需要先发送【选择竞技场订阅+序号】后才可使用**

| 关键词       | 说明                                    |
|:----------|:--------------------------------------|
| 仅下降开/关    | 开:仅推送排名下降信息 关:推送全部                    |
| 全天开/关     | 开:全天推送排名变化信息 关:每天13:00-16:00间推送排名变化信息 |
| 登录提醒开/关   | 开启则推送绑定账号最新在线时间,默认30分钟以上才会推送          |
| 提醒间隔num分钟 | 设置登录提醒的忽略间隔时间                         |
| 提醒排名num名  | 设置在指定排名以内提醒                           |

#### 删除添加的多个订阅

| 关键词       | 说明         |
|:----------|:-----------|
| 删除我的竞技场订阅 | 删除添加过的所有订阅 |

## 管理指令

**以下命令需要bot的主人私聊bot发送触发，其中序号为pcrstatus查询到的客户端序号**

| 关键词           | 说明                               |
|:--------------|:---------------------------------|
| pcrstatus     | 查询各个客户端可用性状态                     |
| pcrstatus 序号  | 查询具体客户端状态（空格必须）                  |
| pcrval 序号 验证码 | 按需手动过客户端验证码 （空格必须）               |
| pcrlogin 序号   | 客户端连续5次出错会自锁，需要手动解除锁定来继续尝试（空格必须） |

# TODO
web管理订阅
