from DB import use_cursor

db, cursor = use_cursor()


def select_all_chat_group() -> tuple:
    sql = "SELECT * FROM `chat_group`;"
    cursor.execute(sql)
    result = cursor.fetchall()
    return result


def select_message_by_grouop_id(group_id) -> tuple:
    sql = "SELECT user_id, context FROM message WHERE group_id=" + str(group_id) + ";"
    cursor.execute(sql)
    result = cursor.fetchall()
    return result


def insert_to_chat_group(group_id, is_start):
    sql = "INSERT INTO chat_group(group_id, is_start) VALUES(" + str(group_id) + ", " + str(is_start) + ");"
    res = cursor.execute(sql)
    db.commit()
    return res


def delete_from_chat_group(group_id):
    sql = 'DELETE FROM chat_group WHERE group_id=' + str(group_id) + ';'
    cursor.execute(sql)
    db.commit()


def find_group_id_from_chat_group(group_id) -> bool:
    sql = "SELECT group_id FROM chat_group where group_id=" + str(group_id) + ';'
    cursor.execute(sql)
    result = cursor.fetchall()
    if len(result) != 1:
        return False
    else:
        return True


def find_is_start_from_chat_group(group_id) -> bool:
    sql = "SELECT is_start FROM chat_group where group_id=" + str(group_id) + ';'
    cursor.execute(sql)
    result = cursor.fetchall()
    if result[0]['is_start'] == 1:
        return True
    else:
        return False


def insert_to_message(group_id, user_id, msg):
    sql = "INSERT INTO message(group_id, user_id, context) VALUES (" \
          + str(group_id) + ", " + str(user_id) + ", \"" + msg + "\");"
    cursor.execute(sql)
    db.commit()


def set_is_start_1(group_id):
    sql = "UPDATE chat_group SET is_start=1 WHERE group_id=" + str(group_id) + ";"
    cursor.execute(sql)
    db.commit()
