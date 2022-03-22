from DB import use_cursor

db, cursor = use_cursor()


def select_all_chat_group() -> tuple:
    sql = "SELECT * FROM `chat_group`;"
    cursor.execute(sql)
    result = cursor.fetchall()
    print(result)
    return result


def insert_to_chat_group(query):
    sql = query
    cursor.execute(sql)
    db.commit()


def update_chat_group(query):
    sql = query  # UPDATE 테이블명 SET 컬럼명=컬럼값 WHERE절
    cursor.execute(sql)
    db.commit()


def delete_from_chat_group(group_id):
    sql = 'DELETE FROM chat_group WHERE group_id=' + str(group_id) + ';'
    cursor.execute(sql)
    db.commit()


def find_group_id_from_chat_group(group_id) -> bool:
    sql = "SELECT group_id FROM chat_group where group_id=" + str(group_id) + ';'
    result = cursor.fetchall()
    print(result)
    if len(result) != 1:
        return False
    else:
        return True
