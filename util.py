import time
from nonebot import get_bot

bot = get_bot()


# 时间转换
def timechange(timestr):
    timestamp = int(timestr)
    timearray = time.localtime(timestamp)
    otherstyletime = time.strftime("%Y-%m-%d %H:%M:%S", timearray)
    return otherstyletime


def timechange2(timestr):
    timestamp = int(timestr)
    timearray = time.localtime(timestamp)
    otherstyletime = time.strftime("%m-%d %H:%M:%S", timearray)
    return otherstyletime

# 名称获取
async def get_user_name(user_id, group_id):
    try:
        user = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        user_name = user['card'] if user['card'] != '' else user['nickname']
        return user_name
    except:
        raise Exception('查询用户资料异常')


async def get_group_name(group_id):
    try:
        group = await bot.get_group_info(group_id=group_id)
        group_name = group['group_name']
        return group_name
    except:
        raise Exception('查询群资料异常')