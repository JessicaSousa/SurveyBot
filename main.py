import utils

import os
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    PollAnswerHandler,
    CallbackQueryHandler,
)


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

CLOSED, OPEN, REGULAR_ANSWER = range(3)

def send_question(update, context):
    next_question = "survey_finish"
    question_id = context.user_data["question_id"]
    current_survey = context.user_data["current_survey"]
    list_size = len(current_survey)

    callback_data = next_question
    if question_id + 1 < list_size:
        if len(current_survey[question_id+1]["options"]) > 1:
            next_question = "closed"
        else:
            next_question = "open"
        callback_data = f"{next_question}_{question_id + 1}"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Próxima", callback_data=callback_data
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message and not update.message.text.startswith("/start"):
        bot_message = update.message.reply_text(
            f"Sua resposta: {update.message.text}",reply_markup=reply_markup
        )
        context.user_data[update.message.message_id] = bot_message.message_id
        context.user_data[bot_message.message_id] = reply_markup
    elif question_id < list_size:
        template = current_survey[question_id]
        question = template["text"]

        if template["required"]:
            question = "❇ " + question

        if len(template["options"]) > 1:
            message = context.bot.send_poll(
                update.effective_user.id,
                question,
                template["options"],
                is_anonymous=False,
                allows_multiple_answers=template["allows_multiple_answers"],
                reply_markup=reply_markup,
            )

            payload = {
                message.poll.id: {
                    "question_id": question_id,
                    "question": template["text"],
                    "options": template["options"],
                    "message_id": message.message_id,
                    "chat_id": update.effective_chat.id,
                    "required": template["required"],
                }
            }
            context.user_data["polls"].append(message.poll.id)
            context.bot_data.update(payload)
        else:
           context.bot.send_message(update.effective_user.id, question)
    return next_question



def start(update, context):
    if context.args:
        bot_name = context.args[0]
        if bot_name in utils._SURVEYS:
            # # Checar se o usuário já respondeu este survey
            # if not utils.is_answered(update.message.from_user.id, bot_name):
            context.user_data["polls"] = []
            context.user_data["question_id"] = 0
            context.user_data["bot_name"] = bot_name
            context.user_data["current_survey"] = utils._SURVEYS[bot_name][
                "questions"
            ]
            N = len(utils._SURVEYS[bot_name]["questions"])
            update.message.reply_text(
                (
                    f"Olá, {update.message.from_user.first_name}, o bot "
                    f"@{bot_name} te encaminhou para que possa avaliá-lo. Eu "
                    f"irei lhe fazer algumas perguntas, serão {N} perguntas "
                    "no total."
                )
            )
            # enviar primeira pergunta
            answer_type = send_question(update, context)
            if context.user_data["current_survey"][0]["options"]:
                if answer_type=="closed":
                    return CLOSED
                elif answer_type=="open":
                    return OPEN
            else:
                return REGULAR_ANSWER

# Função para exibir perguntas com duas ou mais escolhas
def question_with_options(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_reply_markup(None)

    if query.message.message_id in context.user_data:
        context.user_data[query.message.message_id] = None

    _, current_id = query.data.split("_")
    context.user_data["question_id"] = int(current_id)
    answer_type = send_question(update, context)
    if answer_type=="open":
        return OPEN
    else:
        return CLOSED


# Função para exibir perguntas sem opções de escolha
def question_without_options(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_reply_markup(None)
    if query.message.message_id in context.user_data:
        context.user_data[query.message.message_id] = None

    _, current_id = query.data.split("_")
    context.user_data["question_id"] = int(current_id)
    send_question(update, context)
    return REGULAR_ANSWER
    

# Capturar resposta do usuário
def regular_answer(update, context):
    answer_type = send_question(update, context)
    if answer_type=="open":
        return OPEN
    else:
        return CLOSED


def end(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_reply_markup(None)
    if query.message.message_id in context.user_data:
        context.user_data[query.message.message_id] = None

    # Encerrar todas as polls da conversa:
    for poll_id in context.user_data["polls"]:
        context.bot.stop_poll(
            context.bot_data[poll_id]["chat_id"],
            context.bot_data[poll_id]["message_id"],
        )
    context.bot.send_message(update.effective_user.id, "Questionário finalizado!")
    return ConversationHandler.END
 
            
def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# Detectar se usuário editou a mensagem de resposta
def edited(update, context):
    if update.edited_message:
        message_id = update.edited_message.message_id
        message_bot_id = context.user_data[message_id]
        reply_markup = context.user_data[message_bot_id]
        context.bot.edit_message_text(chat_id=update.edited_message.chat.id, 
                          message_id=message_bot_id,
                          text=f"Sua resposta: {update.edited_message.text}",
                          reply_markup=reply_markup)
        


def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    try:
        options = context.bot_data[poll_id]["options"]
    except KeyError:
        return
    selected_options = answer.option_ids
    answer_string = ""
    has_answer = False
    for question_id in selected_options:
        has_answer = True
        if question_id != selected_options[-1]:
            answer_string += options[question_id] + ", "
        else:
            answer_string += options[question_id]
    context.bot_data[poll_id]["has_answer"] = has_answer
    context.bot_data[poll_id]["answer_string"] = answer_string


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text("Help!")


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.getenv("TOKEN"), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher


    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(PollAnswerHandler(receive_poll_answer))

    # Setup conversation handler with the states FIRST and SECOND
    # Use the pattern parameter to pass CallbackQueries with specific
    # data pattern to the corresponding handlers.
    # ^ means "start of line/string"
    # $ means "end of line/string"
    # So ^ABC$ will only allow 'ABC'
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CLOSED: [
                CallbackQueryHandler(question_with_options, pattern='^closed_[0-9]+$'),
                CallbackQueryHandler(end, pattern='^survey_finish$'),
            ],
            OPEN: [
                CallbackQueryHandler(question_without_options, pattern='^open_[0-9]+$'),
                
            ],
            REGULAR_ANSWER: [
                MessageHandler(Filters.regex("^(?!/).*"), regular_answer),
            ]

        },
        fallbacks=[
        CommandHandler('start', start),
        MessageHandler(Filters.regex("^(?!/).*"), edited)],
    )

    # Add ConversationHandler to dispatcher that will be used for handling
    # updates
    dp.add_handler(conv_handler)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()