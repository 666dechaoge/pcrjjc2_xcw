import datetime
import time
from copy import deepcopy
from itertools import groupby
from operator import itemgetter

from nonebot import get_bot

import hoshino
from hoshino import priv
from hoshino.typing import CQHttpError
from hoshino.typing import NoticeSession, MessageSegment
from hoshino.util import pic2b64
from .create_img import generate_info_pic, generate_support_pic
from .jjcbinds import *
from .jjchistory import *
from .pcrlogin import bot, pro_queue, get_avali
from .service import sv
from .util import timechange, timechange2, get_user_name, get_group_name

cool_down = datetime.timedelta(minutes=1)  # 选择冷却时间
expire = datetime.timedelta(minutes=2)  # 选择过期时间

id_user_tmp = {}  # 群用户最近一次选择的订阅id
last_check = {}  # 群用户最近一次选择订阅的时间
cache = {}  # 排名缓存
detail_cache = {}  # 详细查询信息缓存

# 数据库对象初始化
JJCH = JJCHistoryStorage()
JJCB = JJCBindsStorage()


class PriorityEntry(object):

    def __init__(self, priority, data):
        self.data = data
        self.priority = priority

    def __lt__(self, other):
        return self.priority < other.priority


async def not_avail(bot, ev):
    await bot.send(ev, '服务不可用')


# 竞技场绑定
@sv.on_rex(r'^竞技场绑定 ?(\d{1,15})?$')
async def on_arena_bind(bot, ev):
    game_id = ev['match'].group(1)
    if game_id is None:
        await bot.finish(ev, '请输入要绑定的13位id', at_sender=True)
    elif len(game_id) != 13:
        await bot.send(ev, 'id格式有误，请正确输入13位id', at_sender=True)
        return
    user_id = str(ev['user_id'])
    group_id = str(ev['group_id'])
    try:
        result_list_user = JJCB.select_by_user_id(user_id)
        if len(result_list_user) >= 3:
            await bot.send(ev, "最多可以绑定三个游戏ID！")
            return
        a_game_bind = JJCB.select_by_game_id(game_id)
        if a_game_bind:
            old_bind = a_game_bind[0]
            new_bind = {
                'game_id': game_id,
                'user_id': user_id,
                'group_id': group_id,
                # 以下默认开启
                'arena': old_bind['arena'],
                'grand_arena': old_bind['grand_arena'],
                'notify_channel': old_bind['notify_channel'],
                'notify_type': old_bind['notify_type'],
                'all_day': old_bind['all_day'],
                # 以下默认关闭
                'login_notice': old_bind['login_notice'],
                'notice_interval': old_bind['notice_interval']
            }
            if old_bind['user_id'] != user_id:
                await bot.send(ev, '该游戏ID已被其他用户绑定，请联系维护组！')
                return
            JJCB.update(new_bind)
            await bot.send(ev, f'您已绑定过游戏ID{game_id}，已覆盖之前的绑定', at_sender=True)
        else:
            JJCB.add(game_id, user_id, group_id)
        await bot.send(ev, '竞技场绑定添加成功', at_sender=True)
        return
    except Exception as e:
        await bot.send(ev, e)
        return


# 竞技场未绑定回复
async def user_no_bind(bot, ev):
    await bot.send(ev, '未绑定竞技场', at_sender=True)


# 获取查询目标
def get_query_uid(ev):
    if len(ev.message) == 1 and ev.message[0].type == 'text' and not ev.message[0].data['text']:
        user_id = str(ev['user_id'])
        print(f"查询自己{user_id}")
    # 群友代查功能，可选
    elif ev.message[0].type == 'at' and ev.message[0].data['qq'] != 'all':
        user_id = str(ev.message[0].data['qq'])
        print(f"代查他人{user_id}")
    else:
        user_id = str(ev['user_id'])
    return user_id


# 竞技场查询
@sv.on_prefix('竞技场查询')
async def on_query_arena(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await user_no_bind(bot, ev)
        return
    if get_avali():
        for bind in result_list_by_user:
            game_id = bind['game_id']
            pro_entity = PriorityEntry(3, (query_rank, {"game_id": game_id, "user_id": user_id, "ev": ev}))
            await pro_queue.put(pro_entity)
    else:
        await not_avail(bot, ev)


async def query_rank(res_all, no, game_id, user_id, ev):
    msg_list = [f'\nXCW{no}号开始查询QQ:{user_id}\n']
    try:
        # res_all = await queryall(game_id)
        res = res_all['user_info']
        msg_list.append(f'游戏ID：{game_id}\n'
                        f'游戏昵称:{res["user_name"]}\n'
                        f'最新在线时间:{timechange(res["last_login_time"])}\n'
                        f'竞技场排名：{res["arena_rank"]}\n'
                        f'公主竞技场排名：{res["grand_arena_rank"]}')
    except Exception as e:
        await bot.send(ev, f'查询{game_id}出错{e}', at_sender=True)
    msg = ''.join(msg_list)
    await bot.send(ev, msg, at_sender=True)
    return


@sv.on_rex(r'^详细竞技场查询 ?(\d{1,15})?$')
async def on_query_arena_id(bot, ev):
    robj = ev['match']
    game_id = robj.group(1)
    if not game_id:
        await bot.finish(ev, '请输入13位游戏id', at_sender=True)
    if len(game_id) != 13:
        await bot.finish(ev, '游戏id有误，请正确输入13位id', at_sender=True)
        return
    if get_avali():
        await bot.send(ev, '查询ing')
        pro_entity = PriorityEntry(2, (query_info, {"game_id": game_id, "ev": ev}))
        await pro_queue.put(pro_entity)
        return
    else:
        await not_avail(bot, ev)


async def query_info(allres, no, ev):
    try:
        # allres = await queryall(game_id)
        sv.logger.info(f'由{no}号XCW查询，开始生成竞技场查询图片...')  # 通过log显示信息
        result_image = await generate_info_pic(allres)
        result_image = pic2b64(result_image)  # 转base64发送，不用将图片存本地
        result_image = MessageSegment.image(result_image)
        result_support = await generate_support_pic(allres)
        result_support = pic2b64(result_support)  # 转base64发送，不用将图片存本地
        result_support = MessageSegment.image(result_support)
        sv.logger.info('竞技场查询图片已准备完毕！')
        try:
            await bot.send(ev, f"\n{str(result_image)}\n{result_support}", at_sender=True)
        except Exception as e:
            sv.logger.error(f"发送出错，{e}")
    except Exception as e:
        await bot.send(ev, f'查询出错，{e}', at_sender=True)


# 单个订阅删除方法
def delete_game_bind(game_id):
    JJCH.remove(game_id)
    JJCB.remove_by_game_id(game_id)
    sv.logger.info(f'删除游戏ID:{game_id}的竞技场订阅')


# 用户订阅删除方法
def delete_user_bind(user_id):
    results = JJCB.select_by_user_id(user_id)
    if not results:
        return False
    else:
        for result in results:
            game_id = result['game_id']
            JJCH.remove(game_id)
        JJCB.remove_by_user_id(user_id)
        sv.logger.info(f'删除USER_ID:{user_id}的所有竞技场订阅')
        return True


# 群订阅删除方法
def delete_group_bind(group_id):
    results = JJCB.select_by_group_id(group_id)
    if not results:
        return False
    else:
        for result in results:
            game_id = result['game_id']
            JJCH.remove(game_id)
        JJCB.remove_by_group_id(group_id)
        sv.logger.info(f'删除GROUP_ID:{group_id}的所有竞技场订阅')
        return True


@sv.on_prefix('查看竞技场绑定', '查看竞技场订阅', '查看竞技场列表', '竞技场绑定列表', '竞技场订阅列表',
              '查询竞技场绑定',
              '查询竞技场订阅', '查询竞技场列表', )
async def query_binds(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await user_no_bind(bot, ev)
        return
    else:
        msg_list = [f'QQ{user_id}的绑定列表']
        n = 1
        for bind in result_list_by_user:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = game_id
            msg_list.append(f'\n{n}.昵称或者ID:{id_name}\n')
            msg_list.append(f"竞技场绑定ID：{bind['game_id']}\n"
                            f"竞技场绑定群聊：{bind['group_id']}\n"
                            f"战斗竞技场订阅：{'开启' if bind['arena'] else '关闭'}\n"
                            f"公主竞技场订阅：{'开启' if bind['grand_arena'] else '关闭'}\n"
                            f"排名变化推送方式：{'群聊' if bind['notify_channel'] else '私聊'}\n"
                            f"排名推送范围：{'仅下降' if bind['notify_type'] else '推送全部'}\n"
                            f"推送时间范围：{'全天' if bind['all_day'] else '每天13:00-16:00'}\n"
                            f"登录提醒：{'开启' + ',忽略间隔' + str(bind['notice_interval']) + '分钟' if bind['login_notice'] else '关闭'}")
            n = n + 1
        await bot.send(ev, ''.join(msg_list))


# 竞技场订阅设置
@sv.on_prefix('设置竞技场绑定', '设置竞技场订阅', '选择竞技场绑定', '选择竞技场订阅')
async def set_arena_sub(bot, ev):
    global last_check, id_user_tmp
    ids_user_temp = {}  # 单用户绑定列表
    key = f'{ev.group_id}-{ev.user_id}'
    if key in last_check:
        intervals = datetime.datetime.now() - last_check[key]
        if intervals < cool_down:
            await bot.finish(ev, f'冷却中，请{(cool_down - intervals).seconds}秒之后再设置~', at_sender=True)
            return
    result_list_by_user = JJCB.select_by_user_id(ev.user_id)
    if not result_list_by_user:
        await user_no_bind(bot, ev)
        return
    n = 1
    for bind in result_list_by_user:
        game_id = bind['game_id']
        ids_user_temp[str(n)] = game_id
        n = n + 1
    sn = str(ev.message[0])
    if not sn:
        id_user_tmp[key] = ids_user_temp["1"]
        try:
            id_name = cache[id_user_tmp[key]][3]
        except:
            id_name = id_user_tmp[key]
        await bot.send(ev, f'您没有输入序号，默认选择第一个,昵称或ID为{id_name}，有效期2分钟', at_sender=True)
        last_check[key] = datetime.datetime.now()
        return
    elif sn not in ids_user_temp:
        await bot.send(ev, '序号有误', at_sender=True)
        return
    else:
        id_user_tmp[key] = ids_user_temp[sn]
        try:
            id_name = cache[id_user_tmp[key]][3]
        except:
            id_name = id_user_tmp[key]
        last_check[key] = datetime.datetime.now()
        await bot.send(ev, f'已选择要设置的绑定，昵称或ID为{id_name}，有效期2分钟', at_sender=True)


# 检查过期
def if_not_expired(key):
    if key not in id_user_tmp:
        msg = '请先选择要修改的订阅'
        return False, msg
    else:
        intervals = datetime.datetime.now() - last_check[key]
        if intervals > expire:
            msg = '选择过期，请重新选择要修改的订阅'
            return False, msg
        else:
            return True, ''


async def bind_switch(ev, game_id, setting_item_key, value):
    try:
        a_game_bind = JJCB.select_by_game_id(game_id)
        if a_game_bind:
            bind = a_game_bind[0]
            bind[setting_item_key] = value
            JJCB.update(bind)
            return f'{ev["match"].group(0)}成功'
        else:
            return "错误，不存在该订阅"
    except Exception as e:
        return str(e)


async def bind_get(game_id, setting_item_key):
    try:
        a_game_bind = JJCB.select_by_game_id(game_id)
        if a_game_bind:
            bind = a_game_bind[0]
            value = bind[setting_item_key]
            return value
        else:
            return "错误，不存在该订阅"
    except Exception as e:
        return str(e)


# 竞技场订阅删除
@sv.on_prefix('删除竞技场订阅','删除竞技场绑定')
async def delete_arena_sub(bot, ev):
    gid = ev.group_id
    uid = ev.user_id
    key = f'{gid}-{uid}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    game_id = id_user_tmp[key]
    del id_user_tmp[key]
    delete_game_bind(game_id)
    await bot.send(ev, f'删除竞技场订阅{game_id}成功', at_sender=True)
    await send_to_admin(f'群:{gid}的QQ:{uid}竞技场推送订阅{game_id}被删除了')


@sv.on_prefix('删除我的竞技场订阅')
async def delete_arena_sub(bot, ev):
    gid = ev.group_id
    uid = ev.user_id
    key = f'{gid}-{uid}'
    flag = delete_user_bind(uid)
    if not flag:
        await user_no_bind(bot, ev)
    else:
        efficient_flag, err_msg = if_not_expired(key)
        if not efficient_flag:
            pass
        else:
            del id_user_tmp[key]
        await bot.send(ev, '删除全部竞技场订阅成功', at_sender=True)
        await send_to_admin(f'群:{gid}的QQ:{uid}竞技场推送订阅全部被删除了')


# 竞技场订阅调整
@sv.on_rex('(启用|开启|停止|禁用|关闭)(公主)?竞技场订阅')
async def switch_arena(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return

    item_key = 'arena' if ev['match'].group(2) is None else 'grand_arena'
    game_id = id_user_tmp[key]
    value = 1 if ev['match'].group(1) in ('启用', '开启') else 0
    msg = await bind_switch(ev, game_id, item_key, value)
    await bot.send(ev, msg, at_sender=True)


@sv.on_rex('切换(群聊|私聊)')
async def change_notify_channel(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    # 1 群聊 0 私聊
    item_key = 'notify_channel'
    value = 1 if ev['match'].group(1) == '群聊' else 0
    game_id = id_user_tmp[key]

    msg = await bind_switch(ev, game_id, item_key, value)
    await bot.send(ev, msg, at_sender=True)


@sv.on_rex('仅下降(开|关)')
async def change_notify_type(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    # 1 仅下降 0 全部推送
    item_key = 'notify_type'
    game_id = id_user_tmp[key]
    value = 1 if ev['match'].group(1) == '开' else 0

    msg = await bind_switch(ev, game_id, item_key, value)
    await bot.send(ev, msg, at_sender=True)


@sv.on_rex('全天(开|关)')
async def change_all_day(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    # 1 全天 0 击剑时间段
    item_key = 'all_day'
    game_id = id_user_tmp[key]
    value = 1 if ev['match'].group(1) == '开' else 0

    msg = await bind_switch(ev, game_id, item_key, value)
    await bot.send(ev, msg, at_sender=True)


# 登录提醒
@sv.on_rex('登录提醒(开|关)')
async def change_login_notice(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    # 1 开启 0 关闭
    item_key = 'login_notice'
    game_id = id_user_tmp[key]
    value = 1 if ev['match'].group(1) == '开' else 0

    msg = await bind_switch(ev, game_id, item_key, value)
    await bot.send(ev, msg, at_sender=True)


@sv.on_rex(r'提醒间隔(?P<num>\d+)分钟')
async def change_login_interval(bot, ev):
    key = f'{ev.group_id}-{ev.user_id}'
    efficient_flag, err_msg = if_not_expired(key)
    if not efficient_flag:
        await bot.send(ev, err_msg, at_sender=True)
        return
    game_id = id_user_tmp[key]
    # value即分钟数
    value = int(ev['match'].group('num'))
    item_key1 = 'login_notice'
    item_key2 = 'notice_interval'
    login_notice_status = await bind_get(game_id, item_key1)
    if login_notice_status == 0:
        await bot.send(ev, "请先开启该订阅的登录提醒")
        return
    elif login_notice_status == "错误，不存在该订阅":
        msg = login_notice_status
    else:
        msg = await bind_switch(ev, game_id, item_key2, value)
    await bot.send(ev, msg, at_sender=True)


# 竞技场历史
@sv.on_prefix('竞技场历史')
async def send_arena_history(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await user_no_bind(bot, ev)
        return
    else:
        msg_list = [f'QQ:{user_id}']
        for bind in result_list_by_user:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = ''
            msg_list.append('\n')
            msg_list.append(id_name)
            msg_list.append('\n')
            msg_list.append(JJCH.select(game_id, 1))
        await bot.send(ev, ''.join(msg_list), at_sender=True)


@sv.on_prefix('公主竞技场历史')
async def send_parena_history(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await user_no_bind(bot, ev)
        return
    else:
        msg_list = [f'QQ:{user_id}']
        for bind in result_list_by_user:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = ''
            msg_list.append('\n')
            msg_list.append(id_name)
            msg_list.append('\n')
            msg_list.append(JJCH.select(game_id, 0))
        await bot.send(ev, ''.join(msg_list), at_sender=True)


# 向管理员报告
async def send_to_admin(msg):
    await bot.send_private_msg(user_id=hoshino.config.SUPERUSERS[0],
                               message=msg)


# 关键轮询
@sv.scheduled_job('interval', minutes=0.2)
async def on_arena_schedule():
    if get_avali():
        JJCB.refresh()
        bind_cache = deepcopy(JJCB.bind_cache)
        for game_id in bind_cache:
            bind_info = bind_cache[game_id]
            pro_entity = PriorityEntry(10, (compare, {"game_id": game_id, "bind_info": bind_info}))
            await pro_queue.put(pro_entity)
        sv.logger.info(f"query started for {len(bind_cache)} users!")


async def compare(resall, no, bind_info):
    global cache
    game_id = bind_info['game_id']
    group_id = bind_info['group_id']
    user_id = bind_info['user_id']
    try:
        res = resall['user_info']
        res = (
            res['arena_rank'], res['grand_arena_rank'], res['last_login_time'], res['user_name'])
        # print(res)
        if game_id not in cache:
            cache[game_id] = res
            return
            # continue
        last = cache[game_id]
        cache[game_id] = res

        # 游戏昵称变化推送
        if res[3] != last[3]:
            if bind_info['notify_channel']:
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message=f'{no}号XCW检测到[CQ:at,qq={user_id}]所绑定的{game_id}游戏昵称发生变化：{last[3]}->{res[3]}'
                )
            else:
                await bot.send_private_msg(
                    user_id=int(user_id),
                    message=f'{no}号XCW检测到[CQ:at,qq={user_id}]所绑定的{game_id}游戏昵称发生变化：{last[3]}->{res[3]}'
                )

        # 两次间隔排名变化且开启了相关订阅就记录到数据库
        if res[0] != last[0] and bind_info['arena']:
            try:
                JJCH.add(int(game_id), 1, last[0], res[0])
                JJCH.refresh(int(game_id), 1)
                sv.logger.info(f"{no}号XCW检测到{game_id}: JJC {last[0]}->{res[0]}")
            except Exception as e:
                sv.logger.critical(f"sqlite数据库操作异常{e}")
        if res[1] != last[1] and bind_info['grand_arena']:
            try:
                JJCH.add(int(game_id), 0, last[1], res[1])
                JJCH.refresh(int(game_id), 0)
                sv.logger.info(f"{no}号XCW检测到{game_id}: PJJC {last[1]}->{res[1]}")
            except Exception as e:
                sv.logger.critical(f"sqlite数据库操作异常{e}")

        now_localtime = time.strftime("%H:%M:%S", time.localtime())
        # 时间判断
        if "13:00:00" < now_localtime < "16:00:00" or bind_info['all_day']:
            # 开启相关订阅就推送下降变化
            if res[0] > last[0] and bind_info['arena']:
                if bind_info['notify_channel']:
                    await bot.send_group_msg(
                        group_id=int(group_id),
                        message=f'{no}号XCW检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↓降低了{res[0] - last[0]}名。'
                    )
                else:
                    await bot.send_private_msg(
                        user_id=int(user_id),
                        message=f'{no}号XCW检测到您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↓降低了{res[0] - last[0]}名。'
                    )

            if res[1] > last[1] and bind_info['grand_arena']:
                if bind_info['notify_channel']:
                    await bot.send_group_msg(
                        group_id=int(group_id),
                        message=f'{no}号XCW检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↓降低了{res[1] - last[1]}名。'
                    )
                else:
                    await bot.send_private_msg(
                        user_id=int(user_id),
                        message=f'{no}号XCW检测到您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↓降低了{res[1] - last[1]}名。'
                    )

            # 设定为仅下降关时才推送上升变化
            if not bind_info['notify_type']:
                if res[0] < last[0] and bind_info['arena']:
                    if bind_info['notify_channel']:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f'{no}号XCW检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↑上升了{last[0] - res[0]}名。'
                        )
                    else:
                        await bot.send_private_msg(
                            user_id=int(user_id),
                            message=f'{no}号XCW检测到您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↑上升了{last[0] - res[0]}名。'
                        )

                if res[1] < last[1] and bind_info['grand_arena']:
                    if bind_info['notify_channel']:
                        await bot.send_group_msg(
                            group_id=int(group_id),
                            message=f'{no}号XCW检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↑上升了{last[1] - res[1]}名。'
                        )
                    else:
                        await bot.send_private_msg(
                            user_id=int(user_id),
                            message=f'{no}号XCW检测到您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↑上升了{last[1] - res[1]}名。'
                        )

            # 登录提醒，提醒间隔默认为30分钟
            if res[2] - last[2] > bind_info['notice_interval'] * 60 and bind_info['login_notice']:
                if bind_info['notify_channel']:
                    await bot.send_group_msg(
                        group_id=int(group_id),
                        message=f'{no}号XCW检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的账号最新在线时间发生变化：{timechange2(last[2])}->{timechange2(res[2])}'
                    )
                else:
                    await bot.send_private_msg(
                        user_id=int(user_id),
                        message=f'{no}号XCW检测到您所绑定的昵称为{res[3]}的账号最新在线时间发生变化：{timechange2(last[2])}->{timechange2(res[2])}'
                    )

            # 两次最新时间间隔太短，忽略
            elif res[2] != last[2] and bind_info['login_notice']:
                sv.logger.info(f"{no}号XCW检测到{res[3]}的最新时间间隔小于{bind_info['notice_interval']}分钟,忽略")
    except CQHttpError as c:
        sv.logger.error(c)
        try:
            user_name = await get_user_name(user_id=user_id, group_id=group_id)
            group_name = await get_group_name(group_id=group_id)
            sv.logger.error(
                f'群:{group_id} {group_name}的{user_id} {user_name}绑定ID为{game_id}的竞技场信息推送错误\n{c}')
            # 推送失败发信息到群
            await bot.send_group_msg(group_id=int(group_id),
                                     message=f'群:{group_id} {group_name}的{user_id} {user_name}绑定ID为{game_id}的竞技场信息推送错误')
        except Exception as e:
            sv.logger.critical(f'CQHTTPError:f{e}')
            try:
                # 失败信息发送到群也出错，则报告给admin
                await send_to_admin(
                    f'发送到群:{group_id} 的 {user_id} 绑定ID为{game_id}的竞技场信息提醒错误')
            except Exception as e_admin:
                sv.logger.critical(f'向管理员进行竞技场推送错误报告时发生错误：{e_admin}')
    except Exception as e:
        sv.logger.error(f'对{game_id}的检查出错:{e}')


# 相关信息统计
@sv.on_fullmatch('jjc状态统计')
async def send_sub_group(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    gl = sv.enable_group
    dgl = sv.disable_group
    if not is_su:
        msg = '需要超级用户权限'
        await bot.send(ev, msg)
    else:
        e_group_list = []
        for eg in gl:
            try:
                group = await get_bot().get_group_info(group_id=eg)
                e_group_list.append(str(eg) + " " + str(group['group_name']) + "\n")
            except:
                await bot.send(ev, f'群{eg}状态异常')
        msg_e = f"{''.join(e_group_list)}共{len(gl)}个群为启用状态"
        d_group_list = []
        for dg in dgl:
            try:
                group = await get_bot().get_group_info(group_id=dg)
                d_group_list.append(str(dg) + " " + str(group['group_name']) + "\n")
            except:
                await bot.send(ev, f'群{dg}状态异常')
        msg_d = f"{''.join(d_group_list)}共{len(dgl)}个群为禁用状态"
        await bot.send(ev, msg_e + "\n" + msg_d)


@sv.on_fullmatch('jjc群统计')
async def send_sub_config(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    if not is_su:
        msg = '需要超级用户权限'
    else:
        bind_list = JJCB.select_all()
        bind_lite = {}
        for bind in bind_list:
            gid, uid = bind['group_id'], bind['user_id']
            bind_lite.setdefault(gid + uid, {
                'group_id': gid,
                'user_id': uid,
                'game_ids': []
            })['game_ids'].append(bind['game_id'])
        sorted_list = list(bind_lite.values())
        sorted_list.sort(key=itemgetter('group_id'))
        sorted_list_groupby = groupby(sorted_list, itemgetter('group_id'))
        group_msg = []
        n = 0
        for gid, subs in sorted_list_groupby:
            try:
                group = await get_bot().get_group_info(group_id=gid)
                group_name = str(group['group_name'])
                sub_list = list(subs)
                j = 0
                for sub in sub_list:
                    j = j + len(sub['game_ids'])
                group_msg.append(f'{gid} {group_name}，{len(sub_list)}个用户，{j}个订阅\n')
                n = n + 1
            except Exception as e:
                sv.logger.error(e)
        msg = f"{''.join(group_msg)}共{n}个群，{len(JJCB.bind_cache)}个订阅，预计查询用时{0.3 * len(JJCB.bind_cache):.2f}秒"
    await bot.send(ev, msg)


@sv.on_prefix('jjc用户统计')
async def send_sub_user(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    group_id = str(ev.message[0]) if str(ev.message[0]) else ev.group_id
    if not is_su:
        msg = '需要超级用户权限'
    else:
        bind_list = JJCB.select_by_group_id(group_id)
        if not bind_list:
            msg = '该群无人订阅'
        else:
            msg_list = []
            bind_lite = {}
            for bind in bind_list:
                uid = bind['user_id']
                bind_lite.setdefault(uid, {
                    'user_id': uid,
                    'game_ids': []
                })['game_ids'].append(bind['game_id'])
            sorted_list = list(bind_lite.values())
            try:
                group = await get_bot().get_group_info(group_id=group_id)
                group_name = str(group['group_name'])
                for user_bind in sorted_list:
                    user = await bot.get_group_member_info(group_id=group_id, user_id=user_bind["user_id"])
                    user_name = user['card'] if user['card'] != '' else user['nickname']
                    msg_list.append(f"{user_bind['user_id']} {user_name} {len(user_bind['game_ids'])}个订阅\n")
                group_msg = f'查询完毕，{group_id}【{group_name}】，有{len(sorted_list)}个用户'
                msg = ''.join(msg_list) + group_msg
            except:
                await bot.send(ev, f'群{group_id}状态异常')
                return
    await bot.send(ev, msg)


# 被踢或者退群自动删除相关订阅
@sv.on_notice('group_decrease.leave', 'group_decrease.kick', 'group_decrease.kick_me')
async def leave_notice(session: NoticeSession):
    # uid是被踢的人qq号
    uid = str(session.ctx['user_id'])
    gid = str(session.ctx['group_id'])
    sid = str(session.ctx['self_id'])

    # bot被踢
    if uid == sid:
        delete_group_bind(gid)
        await send_to_admin(f'bot退群或被踢，QQ群:{gid}的竞技场推送订阅现已都被删除了')
    else:
        binds = JJCB.select_by_user_id(uid)
        if not binds:
            return
        for bind in binds:
            if bind['group_id'] == gid:
                delete_game_bind(bind['game_id'])
        await send_to_admin(f'QQ:{uid}在群:{gid}的竞技场推送订阅被删除了')


# 清理无效用户配置
@sv.on_fullmatch('jjc无效清理')
async def clean_sub_invalid(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    egl = sv.enable_group
    gl = await bot.get_group_list()
    gl_ids = set()
    for g in gl:
        gl_ids.add(g['group_id'])
    if not is_su:
        msg = '需要超级用户权限'
    else:
        n = 0
        msg_list = []
        group_list = JJCB.select_group()
        for result in group_list:
            gid = result['group_id']
            a = int(gid) not in egl
            b = int(gid) not in gl_ids
            if a or b:
                n = n + 1
                delete_group_bind(gid)
                msg_list.append(f'{gid} ')
        msg = ''.join(msg_list) + f"\n清理完毕，清理了{n}个失效群的订阅"
    await bot.send(ev, msg)


# 清理非活跃用户配置
@sv.on_prefix('jjc非活跃清理')
async def clean_sub_inactive(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    if not is_su:
        msg = '需要超级用户权限'
        await bot.finish(ev, msg)
    else:
        try:
            limit_rank = int(str(ev.message[0]))
            if limit_rank < 50:
                await bot.send(ev, "名次至少要大于等于50")
                return
        except Exception as e:
            sv.logger.error(e)
            await bot.send(ev, '名次输入有误')
            return
        # n = 0
        if get_avali():
            await bot.send(ev, f'开始查询并清理双场名次大于{limit_rank}的用户')
            JJCB.refresh()
            bind_cache = deepcopy(JJCB.bind_cache)
            for game_bind in bind_cache:
                info = bind_cache[game_bind]
                pro_entity = PriorityEntry(5, (
                    nonac_clean, {"game_id": game_bind, "bind_info": info, "limit_rank": limit_rank}))
                await pro_queue.put(pro_entity)
        else:
            await not_avail(bot, ev)


async def nonac_clean(resall, info, limit_rank):
    game_id = info['game_id']
    group_id = info['group_id']
    user_id = info['user_id']
    try:
        # resall = await queryall(game_id)
        res = resall['user_info']
        res = (
            res['arena_rank'], res['grand_arena_rank'], res['last_login_time'], res['user_name'],
            res['viewer_id'])
        if res[0] > limit_rank and res[1] > limit_rank:
            delete_game_bind(game_id)
            await send_to_admin(f'群:{group_id}的QQ:{user_id}竞技场推送订阅{game_id}被删除了')
            await bot.send_group_msg(group_id=int(group_id),
                                     message=f'[CQ:at,qq={user_id}],您绑定的昵称为{res[3]}账号的双场排名均大于{limit_rank},已删除您的订阅')
            # n = n + 1
    except CQHttpError as c:
        sv.logger.error(c)
        try:
            user_name = await get_user_name(user_id, group_id)
            group_name = await get_group_name(group_id)
            sv.logger.error(
                f'群:{group_id} {group_name}的{user_id} {user_name}竞技场清理推送错误{c}')
            await send_to_admin(f'{group_id} {group_name}的{user_id} {user_name}竞技场清理推送错误{c}')
        except Exception as e:
            sv.logger.critical(f'向管理员进行竞技场清理错误报告时发生错误：{type(e)}')
    except Exception as e:
        sv.logger.error(f'对{info["id"]}的检查出错:{e}')
