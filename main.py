import datetime
from copy import deepcopy
from itertools import groupby
from operator import itemgetter

from hoshino import priv
from hoshino.typing import NoticeSession, MessageSegment
from hoshino.util import pic2b64
from .create_img import generate_info_pic, generate_support_pic
from .jjcbinds import *
from .jjchistory import *
from .pcrlogin import pro_queue, get_avali
from .service import sv
from .util import *

expire = datetime.timedelta(minutes=2)  # 选择过期时间

id_user_tmp = {}  # 群用户最近一次选择的订阅id
last_check = {}  # 群用户最近一次选择订阅的时间
cache = {}  # 排名缓存
detail_cache = {}  # 详细查询信息缓存
jjc_fre_cache = set()
pjjc_fre_cache = set()
fre_lock = asyncio.Lock()

status = True
# 数据库对象初始化
JJCH = JJCHistoryStorage()
JJCB = JJCBindsStorage()


class PriorityEntry(object):

    def __init__(self, priority, data):
        self.data = data
        self.priority = priority

    def __lt__(self, other):
        return self.priority < other.priority


# 没有可用的pcr客户端回复
async def send_not_avail(bot, ev):
    await bot.send(ev, '竞技场推送服务不可用')


# 竞技场未绑定回复
async def send_user_no_bind(bot, ev):
    await bot.send(ev, '未绑定竞技场', at_sender=True)


# 获取订阅数量
def get_user_sub(user_id):
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        return 0, None
    else:
        return len(result_list_by_user), result_list_by_user


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
                'notice_interval': old_bind['notice_interval'],
                'notice_rank': old_bind['notice_rank']
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
    num, subs = get_user_sub(user_id)
    if num == 0:
        await send_user_no_bind(bot, ev)
        return
    if get_avali():
        n = 0
        for bind in subs:
            game_id = bind['game_id']
            n = n + 1
            pro_entity = PriorityEntry(3, (query_rank, {"game_id": game_id, "user_id": user_id, "ev": ev, "n": n}))
            await pro_queue.put(pro_entity)
    else:
        await send_not_avail(bot, ev)


async def query_rank(res_all, no, game_id, user_id, ev, n):
    user_name = await get_user_name(user_id, ev.group_id)
    msg_list = [f'\nXCW{no}号查询了{user_name}绑定的第{n}个排名信息\n']
    try:
        # res_all = await queryall(game_id)
        res = res_all['user_info']
        msg_list.append(f'游戏ID：{game_id}\n'
                        f'游戏昵称:{res["user_name"]}\n'
                        f'最新在线时间:{timechange(res["last_login_time"])}\n'
                        f'竞技场排名：{res["arena_rank"]}\n'
                        f'公主竞技场排名：{res["grand_arena_rank"]}')
    except Exception as e:
        await send_to_sender(ev, f'查询{game_id}出错{e}')
    msg = ''.join(msg_list)
    await send_to_sender(ev, msg)
    return


@sv.on_rex(r'^详细竞技场查询 ?(\d{1,15})?$')
async def on_query_arena_id(bot, ev):
    robj = ev['match']
    game_id = robj.group(1)
    if get_avali():
        if not game_id:
            await bot.finish(ev, '请在指令后跟13位游戏id', at_sender=True)
        elif len(game_id) != 13:
            await bot.finish(ev, '游戏id有误，请正确输入13位id', at_sender=True)
        else:
            await bot.send(ev, '查询ing')
            pro_entity = PriorityEntry(2, (query_info, {"game_id": game_id, "ev": ev}))
            await pro_queue.put(pro_entity)
    else:
        await send_not_avail(bot, ev)


async def query_info(allres, no, ev):
    try:
        # allres = await queryall(game_id)
        sv.logger.info(f'由XCW{no}号查询，开始生成竞技场查询图片...')  # 通过log显示信息
        result_image = await generate_info_pic(allres)
        result_image = pic2b64(result_image)  # 转base64发送，不用将图片存本地
        result_image = MessageSegment.image(result_image)
        result_support = await generate_support_pic(allres)
        result_support = pic2b64(result_support)  # 转base64发送，不用将图片存本地
        result_support = MessageSegment.image(result_support)
        sv.logger.info('竞技场查询图片已准备完毕！')
        try:
            await send_to_sender(ev, f"\n{str(result_image)}\n{result_support}")
        except Exception as e:
            sv.logger.error(f"发送出错，{e}")
    except Exception as e:
        await send_to_sender(ev, f'查询出错，{e}')


# 单个订阅删除方法
def delete_game_bind(game_id):
    JJCH.remove(game_id)
    JJCB.remove_by_game_id(game_id)
    sv.logger.info(f'删除游戏ID:{game_id}的竞技场订阅')


# 用户订阅删除方法
def delete_user_bind(user_id: str):
    num, subs = get_user_sub(user_id)
    if num != 0:
        for result in subs:
            game_id = result['game_id']
            JJCH.remove(game_id)
        JJCB.remove_by_user_id(user_id)
        sv.logger.info(f'删除USER_ID:{user_id}的所有竞技场订阅')
    return num


# 群订阅删除方法
def delete_group_bind(group_id: str):
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
    num, subs = get_user_sub(user_id)
    if num == 0:
        await send_user_no_bind(bot, ev)
        return
    else:
        user_name = await get_user_name(user_id, ev.group_id)
        msg_list = [f'{user_name}的绑定列表']
        n = 1
        for bind in subs:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = ''
            msg_list.append(f'\n{n}.游戏昵称:{id_name}\n')
            msg_list.append(f"竞技场绑定ID：{bind['game_id']}\n"
                            f"竞技场绑定群聊：{bind['group_id']}\n"
                            f"战斗竞技场订阅：{'开启' if bind['arena'] else '关闭'}\n"
                            f"公主竞技场订阅：{'开启' if bind['grand_arena'] else '关闭'}\n"
                            f"排名变化推送方式：{'群聊' if bind['notify_channel'] else '私聊'}\n"
                            f"排名推送范围：{'仅下降' if bind['notify_type'] else '推送全部'}\n"
                            f"推送时间范围：{'全天' if bind['all_day'] else '每天13:00-16:00'}\n"
                            f"登录提醒：{'开启' + ',忽略间隔' + str(bind['notice_interval']) + '分钟' if bind['login_notice'] else '关闭'}")
            if bind['notice_rank'] < 15001:
                rank_msg = f"\n提醒排名：{bind['notice_rank']}名及以内才提醒\n"
                msg_list.append(rank_msg)
            else:
                msg_list.append("\n")
            n = n + 1
        await bot.send(ev, ''.join(msg_list))


# 竞技场订阅设置
@sv.on_prefix('设置竞技场绑定', '设置竞技场订阅', '选择竞技场绑定', '选择竞技场订阅')
async def set_arena_sub(bot, ev):
    global last_check, id_user_tmp
    ids_user_temp = {}  # 单用户绑定列表
    key = f'{ev.group_id}-{ev.user_id}'
    num, subs = get_user_sub(ev.user_id)
    if num == 0:
        await send_user_no_bind(bot, ev)
        return
    n = 1
    for bind in subs:
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
            msg = '选择已过期，请重新选择要修改的订阅'
            return False, msg
        else:
            return True, ''


async def bind_switch(bot, ev, game_id, setting_item_key, value):
    try:
        a_game_bind = JJCB.select_by_game_id(game_id)
        if a_game_bind:
            bind = a_game_bind[0]
            bind[setting_item_key] = value
            JJCB.update(bind)
            msg = f'{ev["match"].group(0)}成功'
            await bot.send(ev, msg, at_sender=True)
        else:
            msg = "错误，不存在该订阅"
            await bot.send(ev, msg, at_sender=True)
    except Exception as e:
        msg = str(e)
        await bot.send(ev, msg, at_sender=True)


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


# 获得要设置的game_id,用户单订阅不需要再主动选择
async def get_setting_gameid(bot, ev):
    num, subs = get_user_sub(ev.user_id)
    if num == 0:
        await send_user_no_bind(bot, ev)
        return False, None
    elif num == 1:
        game_id = subs[0]['game_id']
        return True, game_id
    else:
        key = f'{ev.group_id}-{ev.user_id}'
        efficient_flag, err_msg = if_not_expired(key)
        if not efficient_flag:
            await bot.send(ev, err_msg, at_sender=True)
            return False, None
        game_id = id_user_tmp[key]
        return True, game_id


# 删除单个竞技场订阅
@sv.on_prefix('删除竞技场订阅', '删除竞技场绑定')
async def delete_arena_sub(bot, ev):
    gid = ev.group_id
    uid = ev.user_id
    key = f'{gid}-{uid}'
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    try:
        del id_user_tmp[key]
    except Exception as e:
        print(e)
    delete_game_bind(game_id)
    await bot.send(ev, f'删除竞技场订阅{game_id}成功', at_sender=True)


# 删除某个用户全部订阅
@sv.on_prefix('清空竞技场订阅', '清空竞技场绑定')
async def delete_arena_sub(bot, ev):
    gid = ev.group_id
    uid = ev.user_id
    key = f'{gid}-{uid}'
    num = delete_user_bind(uid)
    if num == 0:
        await send_user_no_bind(bot, ev)
    else:
        efficient_flag, err_msg = if_not_expired(key)
        if not efficient_flag:
            pass
        else:
            del id_user_tmp[key]
        await bot.send(ev, f'删除用户{uid}的{num}个竞技场订阅成功', at_sender=True)


# 竞技场订阅调整
@sv.on_rex(r'^(启用|开启|停止|禁用|关闭)(公主)?竞技场订阅$')
async def switch_arena(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    item_key = 'arena' if ev['match'].group(2) is None else 'grand_arena'
    value = 1 if ev['match'].group(1) in ('启用', '开启') else 0
    await bind_switch(bot, ev, game_id, item_key, value)


@sv.on_rex(r'^切换(群聊|私聊)$')
async def change_notify_channel(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    # 1 群聊 0 私聊
    item_key = 'notify_channel'
    value = 1 if ev['match'].group(1) == '群聊' else 0
    if value == 0:
        fl = await get_all_friend_list()
        if ev.user_id not in fl:
            await bot.send(ev, '您不在bot的好友列表，无法切换私聊')
            return
    await bind_switch(bot, ev, game_id, item_key, value)


@sv.on_rex(r'^仅下降(开|关)$')
async def change_notify_type(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    # 1 仅下降 0 全部推送
    item_key = 'notify_type'
    value = 1 if ev['match'].group(1) == '开' else 0

    await bind_switch(bot, ev, game_id, item_key, value)


@sv.on_rex(r'^全天(开|关)$')
async def change_all_day(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    # 1 全天 0 击剑时间段
    item_key = 'all_day'
    value = 1 if ev['match'].group(1) == '开' else 0

    await bind_switch(bot, ev, game_id, item_key, value)


# 登录提醒
@sv.on_rex(r'^登录提醒(开|关)$')
async def change_login_notice(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    # 1 开启 0 关闭
    item_key = 'login_notice'
    value = 1 if ev['match'].group(1) == '开' else 0

    await bind_switch(bot, ev, game_id, item_key, value)


@sv.on_rex(r'^提醒间隔(?P<num>\d+)分钟$')
async def change_login_interval(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
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
        await bot.send(ev, msg, at_sender=True)
    else:
        await bind_switch(bot, ev, game_id, item_key2, value)


@sv.on_rex(r'^提醒排名(?P<num>\d+)名$')
async def change_notice_rank(bot, ev):
    flag, game_id = await get_setting_gameid(bot, ev)
    if not flag:
        return
    # value即排名
    value = int(ev['match'].group('num'))
    item_key = 'notice_rank'
    await bind_switch(bot, ev, game_id, item_key, value)


# 竞技场历史
@sv.on_prefix('竞技场历史')
async def send_arena_history(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await send_user_no_bind(bot, ev)
        return
    else:
        user_name = await get_user_name(user_id, ev.group_id)
        msg_list = [f'\n{user_name}']
        n = 1
        for bind in result_list_by_user:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = ''
            msg_list.append('\n')
            msg_list.append(f'{n}.游戏昵称：{id_name}')
            msg_list.append('\n')
            msg_list.append(JJCH.select(game_id, 1))
            n += 1
        await bot.send(ev, ''.join(msg_list), at_sender=True)


@sv.on_prefix('公主竞技场历史')
async def send_parena_history(bot, ev):
    user_id = get_query_uid(ev)
    result_list_by_user = JJCB.select_by_user_id(user_id)
    if not result_list_by_user:
        await send_user_no_bind(bot, ev)
        return
    else:
        user_name = await get_user_name(user_id, ev.group_id)
        msg_list = [f'\n{user_name}']
        n = 1
        for bind in result_list_by_user:
            game_id = bind['game_id']
            try:
                id_name = cache[game_id][3]
            except:
                id_name = ''
            msg_list.append('\n')
            msg_list.append(f'{n}.游戏昵称：{id_name}')
            msg_list.append('\n')
            msg_list.append(JJCH.select(game_id, 0))
            n += 1
        await bot.send(ev, ''.join(msg_list), at_sender=True)


# 关键轮询
@sv.scheduled_job('interval', minutes=0.2)
async def on_arena_schedule():
    global status
    last_status = status
    status = get_avali()
    if last_status != status:
        if not status:
            await send_all_sv_group(sv, "竞技场推送服务不可用，可能是服务器正在维护或者所有bot账号登录出现问题")
        if status:
            await send_all_sv_group(sv, "竞技场推送服务已恢复")
    if status:
        JJCB.refresh()
        bind_cache = deepcopy(JJCB.bind_cache)
        for game_id in bind_cache:
            bind_info = bind_cache[game_id]
            pro_entity = PriorityEntry(10, (compare, {"game_id": game_id, "bind_info": bind_info}))
            await pro_queue.put(pro_entity)
        sv.logger.info(f"query started for {len(bind_cache)} users!")


@sv.scheduled_job('interval', minutes=15)
async def check_frequent():
    global jjc_fre_cache, pjjc_fre_cache
    sv.logger.info(f"start check frequent")
    async with fre_lock:
        jjc_fre_last = jjc_fre_cache
        pjjc_fre_last = pjjc_fre_cache
        jjc_fre_cache = set(JJCH.recent_jjc_ids())
        pjjc_fre_cache = set(JJCH.recent_pjjc_ids())
    # 需要解除风控集
    jjc_fre_release = jjc_fre_last - jjc_fre_cache
    pjjc_fre_release = pjjc_fre_last - pjjc_fre_cache
    # 新的风控集合
    jjc_fre_new = jjc_fre_cache - jjc_fre_last
    pjjc_fre_new = pjjc_fre_cache - pjjc_fre_last
    if jjc_fre_new:
        sv.logger.info(f"new frequent jjc:{jjc_fre_new}")
        for game_id in jjc_fre_new:
            a_game_bind = JJCB.select_by_game_id(game_id)
            if a_game_bind:
                bind = a_game_bind[0]
                bind['arena'] = 0
                group_id = bind['group_id']
                user_id = bind['user_id']
                JJCB.update(bind)
                msg = f"[CQ:at,qq={user_id}]XCW检测到您绑定的游戏ID{game_id}在15分钟内记录过于频繁，已暂时关闭该ID的竞技场推送，XCW仍会记录变化历史，待下次检测正常后自动恢复，您也可以按照帮助手动开启"
                await send_to_group(group_id=int(group_id), message=msg)
    if pjjc_fre_new:
        sv.logger.info(f"new frequent pjjc:{pjjc_fre_new}")
        for game_id in pjjc_fre_new:
            a_game_bind = JJCB.select_by_game_id(game_id)
            if a_game_bind:
                bind = a_game_bind[0]
                bind['grand_arena'] = 0
                group_id = bind['group_id']
                user_id = bind['user_id']
                JJCB.update(bind)
                msg = f"[CQ:at,qq={user_id}]XCW检测到您绑定的游戏ID{game_id}在15分钟内记录过于频繁，已暂时关闭该ID的公主竞技场推送，XCW仍会记录变化历史，待下次检测正常后自动恢复，您也可以按照帮助手动开启"
                await send_to_group(group_id=int(group_id), message=msg)
    if jjc_fre_release:
        sv.logger.info(f"release frequent jjc:{jjc_fre_release}")
        for game_id in jjc_fre_release:
            a_game_bind = JJCB.select_by_game_id(game_id)
            if a_game_bind:
                bind = a_game_bind[0]
                bind['arena'] = 1
                group_id = bind['group_id']
                user_id = bind['user_id']
                JJCB.update(bind)
                msg = f"[CQ:at,qq={user_id}]XCW检测到您绑定的游戏ID{game_id}在15分钟内记录恢复正常，已自动开启该ID的竞技场订阅"
                await send_to_group(group_id=int(group_id), message=msg)
    if pjjc_fre_release:
        sv.logger.info(f"release frequent pjjc:{pjjc_fre_release}")
        for game_id in pjjc_fre_release:
            a_game_bind = JJCB.select_by_game_id(game_id)
            if a_game_bind:
                bind = a_game_bind[0]
                bind['grand_arena'] = 1
                group_id = bind['group_id']
                user_id = bind['user_id']
                JJCB.update(bind)
                msg = f"[CQ:at,qq={user_id}]XCW检测到您绑定的游戏ID{game_id}在15分钟内记录恢复正常，已自动开启该ID的公主竞技场订阅"
                await send_to_group(group_id=int(group_id), message=msg)


@sv.on_fullmatch('jjc风控列表')
async def get_fre_list(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    if not is_su:
        msg = '需要超级用户权限'
    else:
        async with fre_lock:
            msg = "jjc风控列表：\n"
            if not jjc_fre_cache:
                msg += "无记录\n"
            else:
                for jjc_fre_id in jjc_fre_cache:
                    msg += jjc_fre_id + "\n"
            msg += "pjjc风控列表：\n"
            if not pjjc_fre_cache:
                msg += "无记录\n"
            else:
                for pjjc_fre_id in pjjc_fre_cache:
                    msg += pjjc_fre_id + "\n"
            msg += "查询完毕"
    await bot.send(ev, msg)


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
                await send_to_group(
                    group_id=int(group_id),
                    message=f'XCW{no}号检测到[CQ:at,qq={user_id}]所绑定的{game_id}游戏昵称发生变化：{last[3]}->{res[3]}'
                )
            else:
                await send_to_friend(
                    user_id=int(user_id),
                    message=f'XCW{no}号检测到[CQ:at,qq={user_id}]所绑定的{game_id}游戏昵称发生变化：{last[3]}->{res[3]}'
                )
        async with fre_lock:
            jjc_fre = jjc_fre_cache
            pjjc_fre = pjjc_fre_cache
        # 两次间隔排名变化且开启了相关订阅就记录到数据库
        if res[0] != last[0]:
            if bind_info['arena'] or int(game_id) in jjc_fre:
                try:
                    JJCH.add(int(game_id), 1, last[0], res[0])
                    JJCH.refresh(int(game_id), 1)
                    sv.logger.info(f"XCW{no}号检测到{game_id}: JJC {last[0]}->{res[0]}")
                except Exception as e:
                    sv.logger.critical(f"sqlite数据库操作异常{e}")
        if res[1] != last[1]:
            if bind_info['grand_arena'] or int(game_id) in pjjc_fre:
                try:
                    JJCH.add(int(game_id), 0, last[1], res[1])
                    JJCH.refresh(int(game_id), 0)
                    sv.logger.info(f"XCW{no}号检测到{game_id}: PJJC {last[1]}->{res[1]}")
                except Exception as e:
                    sv.logger.critical(f"sqlite数据库操作异常{e}")

        # 指定排名以外直接忽略
        # 双场提醒都开
        if bind_info['arena'] and bind_info['grand_arena']:
            if res[0] > bind_info['notice_rank'] and res[1] > bind_info['notice_rank']:
                return
        # 只开竞技场提醒
        elif bind_info['arena']:
            if res[0] > bind_info['notice_rank']:
                return
        # 只开公主竞技场提醒
        elif bind_info['grand_arena']:
            if res[1] > bind_info['notice_rank']:
                return
        # 双场提醒都关，直接return
        else:
            return

        now_localtime = get_now_localtime()
        # 时间判断
        if "13:00:00" < now_localtime < "16:00:00" or bind_info['all_day']:
            # 开启相关订阅就推送下降变化
            if res[0] > last[0] and bind_info['arena']:
                if bind_info['notify_channel']:
                    await send_to_group(
                        group_id=int(group_id),
                        message=f'XCW{no}号检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↓降低了{res[0] - last[0]}名。'
                    )
                else:
                    await send_to_friend(
                        user_id=int(user_id),
                        message=f'XCW{no}号检测到您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↓降低了{res[0] - last[0]}名。'
                    )

            if res[1] > last[1] and bind_info['grand_arena']:
                if bind_info['notify_channel']:
                    await send_to_group(
                        group_id=int(group_id),
                        message=f'XCW{no}号检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↓降低了{res[1] - last[1]}名。'
                    )
                else:
                    await send_to_friend(
                        user_id=int(user_id),
                        message=f'XCW{no}号检测到您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↓降低了{res[1] - last[1]}名。'
                    )

            # 设定为仅下降关时才推送上升变化
            if not bind_info['notify_type']:
                if res[0] < last[0] and bind_info['arena']:
                    if bind_info['notify_channel']:
                        await send_to_group(
                            group_id=int(group_id),
                            message=f'XCW{no}号检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↑上升了{last[0] - res[0]}名。'
                        )
                    else:
                        await send_to_friend(
                            user_id=int(user_id),
                            message=f'XCW{no}号检测到您所绑定的昵称为{res[3]}的竞技场排名发生变化：{last[0]}->{res[0]}，↑上升了{last[0] - res[0]}名。'
                        )

                if res[1] < last[1] and bind_info['grand_arena']:
                    if bind_info['notify_channel']:
                        await send_to_group(
                            group_id=int(group_id),
                            message=f'XCW{no}号检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↑上升了{last[1] - res[1]}名。'
                        )
                    else:
                        await send_to_friend(
                            user_id=int(user_id),
                            message=f'XCW{no}号检测到您所绑定的昵称为{res[3]}的公主竞技场排名发生变化：{last[1]}->{res[1]}，↑上升了{last[1] - res[1]}名。'
                        )

            # 登录提醒，提醒间隔默认为30分钟
            if res[2] - last[2] > bind_info['notice_interval'] * 60 and bind_info['login_notice']:
                if bind_info['notify_channel']:
                    await send_to_group(
                        group_id=int(group_id),
                        message=f'XCW{no}号检测到[CQ:at,qq={user_id}]您所绑定的昵称为{res[3]}的账号最新在线时间发生变化：{timechange2(last[2])}->{timechange2(res[2])}'
                    )
                else:
                    await send_to_friend(
                        user_id=int(user_id),
                        message=f'XCW{no}号检测到您所绑定的昵称为{res[3]}的账号最新在线时间发生变化：{timechange2(last[2])}->{timechange2(res[2])}'
                    )

            # 两次最新时间间隔太短，忽略
            elif res[2] != last[2] and bind_info['login_notice']:
                sv.logger.info(f"XCW{no}号检测到{res[3]}的最新时间间隔小于{bind_info['notice_interval']}分钟,忽略")
    except Exception as c:
        sv.logger.error(f'CQHTTPError:{c}')
        try:
            # 推送失败发信息到群
            await send_to_group(group_id=int(group_id),
                                message=f'{c}')
        except Exception as e:
            sv.logger.error(f'CQHTTPError:{e}')
            err_msg = f'群:{group_id}\n' \
                      f'QQ:{user_id}\n' \
                      f'绑定ID:{game_id}' \
                      f'内容:{e}'
            try:
                # 失败信息发送到群也出错，则报告给admin
                await send_to_admin(err_msg)
            except Exception as e_admin:
                sv.logger.critical(f'向管理员进行竞技场推送错误报告时发生错误:{e_admin}')


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
                e_group_list.append(str(eg) + " " + await get_group_name(group_id=eg) + "\n")
            except:
                await bot.send(ev, f'群{eg}状态异常')
        msg_e = f"{''.join(e_group_list)}共{len(gl)}个群为启用状态"
        d_group_list = []
        for dg in dgl:
            try:
                d_group_list.append(str(dg) + " " + await get_group_name(group_id=dg) + "\n")
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
                group_name = await get_group_name(group_id=gid)
                sub_list = list(subs)
                j = 0
                for sub in sub_list:
                    j = j + len(sub['game_ids'])
                group_msg.append(f'{gid} {group_name}，{len(sub_list)}个用户，{j}个订阅\n')
                n = n + 1
            except Exception as e:
                sv.logger.error(e)
        msg = f"{''.join(group_msg)}共{n}个群，{len(JJCB.bind_cache)}个订阅"
    await bot.send(ev, msg)



# 被踢或者退群自动删除相关订阅
@sv.on_notice('group_decrease.leave', 'group_decrease.kick', 'group_decrease.kick_me')
async def leave_notice(session: NoticeSession):
    # uid是被踢的人qq号
    ev = session.event
    uid = ev.user_id
    sid = ev.self_id
    gid = ev.group_id

    # bot被踢
    if uid == sid:
        gl_ids = await get_all_group_list()
        if gid not in gl_ids:
            delete_group_bind(str(gid))
            await send_to_admin(f'bot退群或被踢，且再无其他机器人QQ在此群，群:{gid}的竞技场推送订阅现已都被删除')
    else:
        binds = JJCB.select_by_user_id(uid)
        if not binds:
            return
        for bind in binds:
            if bind['group_id'] == str(gid):
                delete_game_bind(bind['game_id'])


# 清理无效用户配置
@sv.on_fullmatch('jjc无效清理')
async def clean_sub_invalid(bot, ev):
    is_su = priv.check_priv(ev, priv.SUPERUSER)
    if not is_su:
        msg = '需要超级用户权限'
    else:
        egl = sv.enable_group
        gl_ids = await get_all_group_list()
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
