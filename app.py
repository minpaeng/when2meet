from telegram import Update, Bot
from telegram.ext import Updater, CallbackContext
from telegram.ext import CommandHandler
from DB import queries


def read_token(file_path):
    f = open(file_path, mode='r', encoding='utf-8')
    s = f.readline()
    return s


def start(update: Update, context: CallbackContext) -> None:
    # update.message.reply_text(f'Hello {update.effective_user.first_name}')
    text = update.message.text
    update.message.reply_text("대화를 시작하세요.\n\"done\"을 입력하면 대화를 마치고, \n\
내용을 분석하여 다함께 만날 수 있는 날을 요약해 줍니다.")
    # if !queries.find_group_id_from_chat_group():
        # queries.insert_to_chat_group("")


def done(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("다함께 만날 수 있는 시간은 아래와 같습니다.\n\n\
1순위\n2022-03-31-00:00~2022-03-31-24:00\n\n\
2순위\n2022-03-29-00:00~2022-03-29-24:00")


token = read_token("token.txt")
# bot = Bot(token=token)
updater = Updater(token)
commands = updater.bot.commands
print(commands)

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('done', done))
updater.start_polling()
updater.idle()

# chat_id = bot.getUpdates()[-1].message.chat.id
# chat_text = bot.getUpdates()[-1].message.text
# bot.sendMessage(chat_id=chat_id, text="test")
# print(chat_id)
# print(chat_text)


# @bot.message_handler(func=lambda message: True)
# def echo_all(message):
#     bot.reply_to(message, message.text)
