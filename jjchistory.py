import os
import sqlite3
import threading

JJCHistory_DB_PATH = os.path.expanduser('~/.hoshino/jjchistory.db')


class JJCHistoryStorage:
    def __init__(self):
        os.makedirs(os.path.dirname(JJCHistory_DB_PATH), exist_ok=True)
        self.lock = threading.Lock()
        self._create_table()

    @staticmethod
    def _connect():
        return sqlite3.connect(JJCHistory_DB_PATH)

    def _create_table(self):
        with self.lock:
            try:
                self._connect().execute('''CREATE TABLE IF NOT EXISTS JJCHistoryStorage
                    (ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                     UID INT  NOT NULL, /* 游戏ID */ 
                     DATETIME DATETIME DEFAULT(datetime('now','localtime')),/* 时间 */
                     ITEM INT NOT NULL, /* 竞技场1，公主竞技场0*/
                     BEFORE INT NOT NULL, /* 变化前 */
                     AFTER INT NOT NULL /* 变化后 */
                      )
                    '''
                                        )
            except Exception as e:
                raise Exception('创建JJCHistory表失败')
            finally:
                self._connect().close()

    def add(self, uid, item, before, after):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute('''INSERT INTO JJCHistoryStorage (UID,ITEM,BEFORE,AFTER)
                VALUES (?,?,?,?)'''
                             , (uid, item, before, after))
                conn.commit()
            except Exception as e:
                raise Exception('新增记录异常')
            finally:
                conn.close()

    def refresh(self, UID, ITEM):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute('''delete from JJCHistoryStorage
    where ID in
    (select ID from JJCHistoryStorage 
    where UID=? and ITEM = ?
    order by DATETIME desc 
    limit(select count(*) FROM JJCHistoryStorage WHERE UID = ? and ITEM = ?) offset 10)
                ''', (UID, ITEM, UID, ITEM))
                conn.commit()
            except Exception as e:
                raise Exception('更新记录异常')
            finally:
                conn.close()

    def select(self, UID, ITEM):
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            try:
                if ITEM == 1:
                    item_name = '竞技场'
                else:
                    item_name = '公主竞技场'
                result = cur.execute('''
                select * from JJCHistoryStorage WHERE UID=? and ITEM = ? ORDER  BY DATETIME desc''', (UID, ITEM))
                result_list = list(result)
                if len(result_list) != 0:
                    msg = f'竞技场绑定ID:{UID}\n{item_name}历史记录'
                    for row in result_list:
                        if row[4] > row[5]:
                            jjc_msg = f'\n{row[2]}:{row[4]}->{row[5]},↑{row[4] - row[5]}'
                        else:
                            jjc_msg = f'\n{row[2]}:{row[4]}->{row[5]},↓{row[5] - row[4]}'
                        msg = msg + jjc_msg
                    return msg
                else:
                    msg = f'竞技场绑定ID:{UID}\n{item_name}历史记录\n无记录'
                    return msg
            except Exception as e:
                raise Exception('查找记录异常')
            finally:
                conn.close()

    def remove(self, UID):
        with self.lock:
            conn = self._connect()
            try:
                conn.execute('delete from JJCHistoryStorage where UID = ?', (UID,))
                conn.commit()
            except Exception as e:
                raise Exception('移除记录异常')
            finally:
                conn.close()
