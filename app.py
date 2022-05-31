from telegram import Update
from telegram.ext import Updater, CallbackContext
from telegram.ext import CommandHandler, MessageHandler, Filters
from DB import queries
import model
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
    chat_type, group_id, _, _ = chat_info(msg)

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
    chat_type, group_id, _, _ = chat_info(msg)

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
        res = model_setting(res1, res2)
        if res == "x":
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="다함께 만날 수 있는 시간이 없습니다.\n")
        elif res == "o":
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="모두 만날 수 있음.\n")
        # chat_group과 message 테이블에서 해당 그룹 아이디와 관련된 값 모두 삭제
        else:
            update.message.reply_text(reply_to_message_id=msg.message_id,
                                      text="다함께 만날 수 있는 시간은 아래와 같습니다.\n\n" + res)

        queries.delete_from_chat_group(group_id)


# start 명령어 호출 후 실행되는 메소드
# 1) 그룹 아이디, 유저 아이디, 메세지 내용을 받아서 DB에 저장
def receive_msg(update: Update, context: CallbackContext) -> None:
    msg = update.message
    _, group_id, user_id, text = chat_info(msg)
    if not queries.find_group_id_from_chat_group(group_id):
        return
    queries.insert_to_message(group_id=group_id, user_id=user_id, msg=text)


def chat_info(message):
    chat_type = message.chat.type
    group_id = message.chat.id
    user_id = message.from_user.id
    chat = message.text
    return chat_type, group_id, user_id, chat


def model_setting(input_sentences, input_person) -> str:
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
    result = when_to_meet(dialogue)

    print()
    print("<결과>")

    result = result.datetimes
    print(result)
    if result is None:
        return "x"
    elif len(result) == 0:
        return "o"
    else:
        tmp_day = []
        for one_datetime in result:
            tmp_day.append(One_day(one_datetime))
        result = tmp_day

        tmp = ""
        result.sort()
        print(result)
        for s in result:
            # print(s.year)
            tmp += str(s) + "\n\n"

        res = tmp
        return res


token = read_token("token.txt")
updater = Updater(token)

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('done', done))
updater.dispatcher.add_handler(MessageHandler(Filters.text, receive_msg))
updater.start_polling()
updater.idle()
