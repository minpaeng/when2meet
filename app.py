from telegram import Update
from telegram.ext import Updater, CallbackContext
from telegram.ext import CommandHandler, MessageHandler, Filters
from DB import queries
import model
import definitions
import datetime as dt
from main import when_to_meet, One_day


def read_token(file_path):
    f = open(file_path, mode='r', encoding='utf-8')
    s = f.readline()
    return s


# start 명령어
# 1) chat - id(그룹일 때 음수일 수 있음) 조회
# 2) chat_group 테이블에 그룹 아이디가 존재하는지 확인
# 3) 존재한다면 is_start가 false인지 확인 후 true로 바꿔줌
# 4) 존재하지 않는다면 Group 테이블에 그룹 추가(isStart는 true로 설정하여 추가)
# 5) 예외처리: is_start가 true 상태라면 start 명령어를 중복호출한 것이므로 end명령어를 입력할 차례라고 안내
# 6) 예외처리: chat_type이 private일 때 어떻게 처리할것인가? 1) 혼자서 대화 진행 가능하도록 2) 둘 이상 단체 채팅에서 사용하라고 경고
def start(update: Update, context: CallbackContext) -> None:
    # 1) chat - id(그룹일 때 음수일 수 있음) 조회
    msg = update.message
    chat_type, group_id, _, _, _ = chat_info(msg)

    # 6) 예외처리: chat_type이 private일 때 어떻게 처리할것인가? 1) 혼자서 대화 진행 가능하도록 2) 둘 이상 단체 채팅에서 사용하라고 경고
    if chat_type == "private":
        update.message.reply_text("그룹 채팅방에서 서비스를 이용해주세요.")
        return

    # 2) chat_group 테이블에 그룹 아이디가 존재하는지 확인
    # 3) 존재한다면 is_start가 false인지 확인 후 true로 바꿔줌
    if queries.find_group_id_from_chat_group(group_id):
        print("group_id 존재: " + str(group_id))
        # 5) 예외처리: is_start가 true 상태라면 start 명령어를 중복호출한 것이므로 end명령어를 입력할 차례라고 안내
        if queries.find_is_start_from_chat_group(group_id):
            update.message.reply_text("start 명령어가 실행중입니다. 대화를 진행해주세요.")
            return
        else:
            queries.set_is_start_1(group_id)
    else:
        res = queries.insert_to_chat_group(group_id, 1)
        print("group_id 삽입 완료: {}".format(res))

    update.message.reply_text("대화를 시작하세요.\n\"done\"을 입력하면 대화를 마치고, \n\
    내용을 분석하여 다함께 만날 수 있는 날을 요약해 줍니다.")


# end 명령어
# 1) chat - id(그룹일 때 음수일 수 있음) 조회
# 2) chat_group 테이블에 그룹 아이디가 존재하는지 확인
# 3) 존재한다면 is_start가 true인지 확인: false라면 start 명령어를 먼저 호출해야 한다고 안내
#                        (start 명령어를 통해 대화 시작 후 end 명령어를 입력하면 약속 시간을 알려줍니다! 하는 내용의 안내)
# 4) 해당 group_id의 메세지를 모두 조회하여 user_id와 함께 모델에 전송 후 chat_group에서 삭제
# 5) 예외처리: is_start가 false라면 start 명령어를 먼저 호출해야 한다고 안내
# 6) 예외처리: chat_type이 private일 때 어떻게 처리할것인가? 1) 혼자서 대화 진행 가능하도록 2) 둘 이상 단체 채팅에서 사용하라고 경고
def done(update: Update, context: CallbackContext) -> None:
    # 1) chat - id(그룹일 때 음수일 수 있음) 조회
    msg = update.message
    chat_type, group_id, _, _, _ = chat_info(msg)

    # 6) 예외처리: chat_type이 private일 때 어떻게 처리할것인가? 1) 혼자서 대화 진행 가능하도록 2) 둘 이상 단체 채팅에서 사용하라고 경고
    if chat_type == "private":
        update.message.reply_text("그룹 채팅방에서 서비스를 이용해주세요.",
                                  reply_to_message_id=msg.message_id)
        return

    # 2) chat_group 테이블에 그룹 아이디가 존재하는지 확인
    if not queries.find_group_id_from_chat_group(group_id):
        print("{}번 group_id 없음: ".format(str(group_id)))
        update.message.reply_text("start 명령어를 먼저 호출한 후 대화를 시작해야 합니다.",
                                  reply_to_message_id=msg.message_id)
        return

    # 3) 존재한다면 is_start가 true인지 확인: false라면 start 명령어를 먼저 호출해야 한다고 안내
    if not queries.find_is_start_from_chat_group(group_id):
        update.message.reply_text("start 명령어를 먼저 호출한 후 대화를 시작해야 합니다.",
                                  reply_to_message_id=msg.message_id)
        return
    else:
        # 그룹 아이디에 해당하는 대화를 DB에서 가져옴
        res = queries.select_message_by_grouop_id(group_id)

        res1, res2 = [], []
        for x in res:
            res1.append(x['context'])
            res2.append(x['user_id'])
        # print("res1", res1)
        # print("res2", res2)

        # 모델에 대화 넘기고 결과 받아오기
        res, date_res, time_res = model_setting(res1, res2, group_id)
        queries.delete_from_message(group_id)
        if res == "x":
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="다함께 만날 수 있는 시간이 없습니다.\n")
        elif res == "o":
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="모두 만날 수 있어요!\n")
        # chat_group과 message 테이블에서 해당 그룹 아이디와 관련된 값 모두 삭제
        else:
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="다함께 만날 수 있는 시간은 아래와 같습니다.\n\n" + res)
        # 사용할 도메인 주소
        url = "http://when2meet.shop:8080/calendar?group_id=" + str(group_id) + "&date=" + date_res + "&time=" + time_res
        print(url)
        update.message.reply_text(reply_to_message_id=msg.message_id,
                                  text="아래 링크에서 보다 자세하게 확인해 보세요.\n" + url)

        queries.set_is_start_0(group_id)


# start 명령어 호출 후 실행되는 메소드
# 1) 그룹 아이디, 유저 아이디, 메세지 내용을 받아서 DB에 저장
def receive_msg(update: Update, context: CallbackContext) -> None:
    msg = update.message
    _, group_id, user_id, text, name = chat_info(msg)
    if not queries.find_group_id_from_chat_group(group_id):
        return
    queries.insert_to_message(group_id=group_id, user_id=user_id, msg=text, name=name)


def chat_info(message):
    chat_type = message.chat.type
    group_id = message.chat.id
    user_id = message.from_user.id
    chat = message.text
    name = message.from_user.first_name
    return chat_type, group_id, user_id, chat, name


def model_setting(input_sentences, input_person, group_id) -> (str, str, str):
    inputs = input_sentences

    inputs_person = input_person

    # ner 추출
    ner = model.ner_model(inputs)
    ner = model.postprocess_NER(ner)
    print(len(inputs), len(ner))
    print(ner)

    # intent 추출
    intent = model.intent_model(inputs)
    print(intent)

    dialogue = [{'person': one_person, 'ner': one_ner, 'intent': one_intent} for one_person, one_ner, one_intent in
                zip(inputs_person, ner, intent)]

    # result = when_to_meet(dialogue)

    TODAY = dt.datetime.now()
    result, speakers = when_to_meet(dialogue)
    # person_ID, one_day
    # 1.없는 경우 = None -> 아예 리스트에 추가하지 않음
    # 2.다 되는 경우 = 현재 날짜(TODAY)로 부터 30일간을 다 넣어줌
    speakers_list = []

    # speakers = {name(person ID): person(When2meet 객체)}

    for name, person in speakers.items():
        if person.datetimes is None:  # 1.없는 경우 = None -> 아예 리스트에 추가하지 않음
            pass
        elif person.datetimes == []:  # 2.다 되는 경우 = 현재 날짜(TODAY)로 부터 30일간을 다 넣어줌
            person.final_set()
            for i in range(1, 31):
                # begin_DT, end_DT, begin_TI, end_TI = one_day
                t_d = TODAY + dt.timedelta(days=i)
                all_DT = definitions.Mydate(year=t_d.year, month=t_d.month, day=t_d.day)
                begin_TI = definitions.Mytime(hour=0)
                end_TI = definitions.Mytime(hour=24)
                tmp_one_day = One_day((all_DT, all_DT, begin_TI, end_TI))
                speakers_list.append({"name": name[1:], "date": tmp_one_day})

        else:  # 3. 해당 날짜만 되는 경우
            person.final_set()
            for one_datetime in person.datetimes:
                speakers_list.append({"name": name[1:], "date": One_day(one_datetime)})

    print("최종 화자들:", speakers_list)

    print()
    print("<결과>")

    result = result.datetimes
    print(result)

    tmp_day = []
    for one_datetime in result:
        tmp_day.append(One_day(one_datetime))
    result = tmp_day

    tmp = ""
    result.sort()
    tmp2 = []  # 2022-06-02같은 포멧으로 결과를 배열에 저장하기 위한 리스트 선언
    for s in result:
        tmp2.append(
            "{}-{}-{}T{}:{}~{}:{}".format(s.str_year, s.str_month, s.str_day, s.str_begin_hour, s.str_begin_minute,
                                          s.str_end_hour, s.str_end_minute))
        tmp += str(s) + "\n\n"

    real_real_tmp = []

    for ss in speakers_list:
        s = ss['date']
        real_tmp = dict()
        real_tmp['name'] = ss['name']
        real_tmp['date'] = "{}-{}-{}T{}:{}~{}:{}".format(s.str_year, s.str_month, s.str_day, s.str_begin_hour,
                                                         s.str_begin_minute, s.str_end_hour, s.str_end_minute)
        real_real_tmp.append(real_tmp)

    if result is None:
        date, time = queries.insert_to_appointment(group_id, tmp2, real_real_tmp)
        return "x", date, time
    elif len(result) == 0:
        date, time = queries.insert_to_appointment(group_id, tmp2, real_real_tmp)
        return "o", date, time
    else:
        date, time = queries.insert_to_appointment(group_id, tmp2, real_real_tmp)
        res = tmp
        return res, date, time


token = read_token("token.txt")
updater = Updater(token)

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('done', done))
updater.dispatcher.add_handler(MessageHandler(Filters.text, receive_msg))
updater.start_polling()
updater.idle()
