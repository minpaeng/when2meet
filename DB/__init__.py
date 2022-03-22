import pymysql
import pymysql.cursors


def db_connect():
    connection = pymysql.connect(
        user='minjeong',
        passwd='asdf123**',
        host='freelec-springboot2-webservice.cc4nd3fpcvep.ap-northeast-2.rds.amazonaws.com',
        db='when2meet',
        charset='utf8'
    )
    return connection


def use_cursor():
    juso_db = db_connect()
    cursor = juso_db.cursor(pymysql.cursors.DictCursor)
    return juso_db, cursor
