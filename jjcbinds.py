import os
import sqlite3
import threading

JJCBinds_DB_PATH = os.path.expanduser('~/.hoshino/jjcbinds.db')


class JJCBindsStorage:
    def __init__(self):
        self.bind_cache = None
        os.makedirs(os.path.dirname(JJCBinds_DB_PATH), exist_ok=True)
        self.lock = threading.Lock()
        # self.cache_lock = Lock()
        self._create_table()

    @staticmethod
    def _connect():
        return sqlite3.connect(JJCBinds_DB_PATH)

    def _create_table(self):
        with self.lock:
            try:
                self._connect().execute('''CREATE TABLE IF NOT EXISTS JJCBinds
                    (ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,/* 主键，自动增加*/
                     GAME_ID TEXT  NOT NULL UNIQUE, /* 游戏ID，添加唯一约束 */
                     USER_ID TEXT NOT NULL, /* 绑定QQ */
                     GROUP_ID TEXT NOT NULL, /* 绑定群 */
                     ARENA INT NOT NULL DEFAULT 1, /* 竞技场开关 */
                     GRAND_ARENA INT NOT NULL DEFAULT 1, /* 公主竞技场开关 */
                     NOTIFY_CHANNEL INT NOT NULL DEFAULT 1, /* 通知渠道 群聊1，私聊0*/
                     NOTIFY_TYPE INT NOT NULL DEFAULT 1, /* 通知类型 仅下降1，全部0*/
                     ALL_DAY INT NOT NULL DEFAULT 1, /* 通知时间范围 全天 1,下午13:00-16:00 0*/
                     LOGIN_NOTICE INT NOT NULL DEFAULT 0, /* 登录提醒 */
                     NOTICE_INTERVAL INT NOT NULL DEFAULT 30,/* 提醒时间间隔 */
                     NOTICE_RANK INT NOT NULL DEFAULT 15001 /* 指定排名以内提醒 */
                      )
                    '''
                                        )
            except Exception as e:
                raise Exception(f'创建JJCBinds表失败{e}')
            finally:
                self._connect().close()

    def add(self, game_id, user_id, group_id):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute('''INSERT INTO JJCBinds (GAME_ID, USER_ID, GROUP_ID)
                VALUES (?,?,?)'''
                             , (game_id, user_id, group_id))
                conn.commit()
            except Exception as e:
                raise Exception(f'新增记录异常{e}')
            finally:
                conn.close()

    def update(self, bind: dict):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute('''UPDATE JJCbinds SET USER_ID = ?,GROUP_ID=?, ARENA=?,GRAND_ARENA=?,
                NOTIFY_CHANNEL=?,NOTIFY_TYPE=?,ALL_DAY=?,LOGIN_NOTICE=?,NOTICE_INTERVAL=?,NOTICE_RANK=?
                WHERE GAME_ID = ?
                ''', (
                    bind['user_id'], bind['group_id'], bind['arena'], bind['grand_arena'], bind['notify_channel'],
                    bind['notify_type'],
                    bind['all_day'], bind['login_notice'], bind['notice_interval'], bind['notice_rank'], bind['game_id']
                )
                             )
                conn.commit()
            except Exception as e:
                raise Exception(f'更新记录异常{e}')
            finally:
                conn.close()

    # 查询基本方法，有重写
    def _select(self, sql: str, *args):
        with self.lock:
            conn = self._connect()

            # 重写方法，查询结果能够返回key为小写字母的字典数组
            # [{'id': 1, ... ,'notice_interval': 30},...]
            def dict_factory(cursor, row):
                d = {}
                for idx, col in enumerate(cursor.description):
                    d[str.lower(col[0])] = row[idx]
                return d

            conn.row_factory = dict_factory
            cur = conn.cursor()
            try:
                cursor = cur.execute(sql, args)
                binds = []
                for row in cursor:
                    binds.append(row)
                return binds
            except Exception as e:
                raise Exception(f'查询记录异常{e}')
            finally:
                conn.close()

    def select_all(self):
        sql = 'select * from JJCBinds'
        return self._select(sql=sql)

    def select_by_game_id(self, game_id):
        sql = 'select * from JJCBinds WHERE GAME_ID=?'
        return self._select(sql, game_id)

    def select_by_user_id(self, user_id):
        sql = 'select * from JJCBinds WHERE USER_ID =?'
        return self._select(sql, user_id)

    def select_by_group_id(self, group_id):
        sql = 'select * from JJCBinds where GROUP_ID = ?'
        return self._select(sql, group_id)

    def _remove(self, sql: str, *args):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute(sql, args)
                conn.commit()
            except Exception as e:
                raise Exception(f'移除记录异常{e}')
            finally:
                conn.close()

    def select_group(self):
        sql = 'select distinct GROUP_ID from JJCBinds'
        return self._select(sql=sql)

    def remove_by_game_id(self, game_id):
        sql = 'delete from JJCBinds where GAME_ID = ?'
        self._remove(sql, game_id)

    # 在单用户多绑定情况下移除该用户全部订阅
    def remove_by_user_id(self, user_id):
        sql = 'delete from JJCBinds where USER_ID = ?'
        self._remove(sql, user_id)

    # 删除某个群全部订阅
    def remove_by_group_id(self, group_id):
        sql = 'delete from JJCBinds where GROUP_ID = ?'
        self._remove(sql, group_id)

    def _execute(self, sql: str, *args):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute(sql, args)
                conn.commit()
            except Exception as e:
                raise Exception(f'{sql}操作记录异常{e}')
            finally:
                conn.close()

    def refresh(self):
        # 最终查询结果能够存储键为游戏ID，值为设定项的字典
        # {
        # '1208649694720': {'ID': 1 , ... ,'NOTICE_INTERVAL': 30},...
        # }
        binds = self.select_all()
        bind_dict = {}
        for bind in binds:
            bind_dict[bind['game_id']] = bind
        self.bind_cache = bind_dict
