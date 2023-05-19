from .safeservice import SafeService
from hoshino import priv

# 帮助信息
sv_help = '''竞技场推送帮助

【竞技场绑定ID】 最多可绑定3个，默认双场启用、通过群聊、仅排名降低时推送

【竞技场查询(@某人）】 默认查询自己，带@查询指定的群员

【查询竞技场列表（@某人）】 查看竞技场绑定列表，默认查询自己，带@查询指定群员

【详细竞技场查询ID】查询详细信息

【(公主)竞技场历史】查询最近10条（公主）竞技场变化记录(只有bot的PCR账号在线期间的数据)

进阶设置项帮助(双场开关/群聊私聊/订阅删除)请发送【竞技场推送进阶帮助】获取

高级设置项帮助(登录提醒/上升变化/推送时间)请发送【竞技场推送高级帮助】获取
'''

sv_help_adv = '''竞技场进阶设置
【清空竞技场订阅】清空自己的竞技场订阅

以下命令用户如果有多个订阅需要先发送【选择竞技场订阅】+序号后才可使用

【开启/启用/停止/关闭（公主）竞技场订阅】 启用/停止战斗或者公主竞技场排名变动推送

【删除竞技场订阅】删除选定的单个订阅

【切换群聊】排名变化信息发送到群
【切换私聊】排名变化信息私聊发送给你(需要你为bot的好友)
'''

sv_help_sup = '''竞技场高级设置
以下命令用户如果有多个订阅需要先发送【选择竞技场订阅】+序号后才可使用

【仅下降开】仅推送排名下降信息
【仅下降关】推送全部变化信息

【全天开】全天推送排名变化信息
【全天关】每天13:00-16:00间推送排名变化信息

【登录提醒开/关】通过群聊推送绑定账号在线时间(北京时间)以及昵称变化,默认两次间隔在30分钟以上才会推送

【提醒间隔X分钟】设置登录提醒的忽略间隔

【提醒排名x名】设置订阅目标只有在指定排名以内才会提醒,默认取值15001
'''

sv_help_svc = '''发 竞技场推送帮助
发 竞技场推送帮助
发 竞技场推送帮助'''
# 服务定义
sv = SafeService('竞技场推送', help_=sv_help, bundle='pcr订阅', enable_on_default=False, manage_priv=priv.SUPERUSER)


@sv.on_fullmatch('竞技场推送帮助', only_to_me=False)
async def send_jjchelp(bot, ev):
    await bot.send(ev, sv_help)


@sv.on_fullmatch('竞技场推送进阶帮助', only_to_me=False)
async def send_jjchelp2(bot, ev):
    await bot.send(ev, sv_help_adv)


@sv.on_fullmatch('竞技场推送高级帮助', only_to_me=False)
async def send_jjchelp3(bot, ev):
    await bot.send(ev, sv_help_sup)


@sv.on_fullmatch('竞技场帮助', only_to_me=False)
async def send_jjchelp(bot, ev):
    await bot.send(ev, sv_help_svc)
