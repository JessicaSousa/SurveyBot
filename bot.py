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

NEXT = 1


def send_survey(update, context):
    question_id = context.user_data["question_id"]
    current_survey = context.user_data["current_survey"]

    list_size = len(current_survey)

    if question_id < list_size:
        template = current_survey[question_id]

        question = template["text"]

        if template["required"]:
            question = "❇ " + question

        if len(template["options"]) > 1:

            keyboard = [
                [
                    InlineKeyboardButton(
                        "Confirmar!", callback_data=question_id + 1
                    )
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

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
            context.bot_data.update(payload)
        else:
            context.bot.send_message(update.effective_user.id, question)
    else:
        context.bot.send_message(
            update.effective_user.id,
            "Agradeço por ter disponibilizado seu tempo para avaliar o bot!",
        )
        print("conversa finalizada")
        return ConversationHandler.END
    return NEXT


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    if context.args:
        bot_name = context.args[0]
        if bot_name in utils._SURVEYS:
            # Checar se o usuário já respondeu este survey
            if not utils.is_answered(update.message.from_user.id, bot_name):
                context.user_data["bot_name"] = bot_name
                context.user_data["current_survey"] = utils._SURVEYS[bot_name][
                    "questions"
                ]
                context.user_data["question_id"] = 0

                N = len(utils._SURVEYS[bot_name]["questions"])
                update.message.reply_text(
                    (
                        f"Olá, {update.message.from_user.first_name}, o bot "
                        f"@{bot_name} te encaminhou para que possa avaliá-lo. Eu "
                        f"irei lhe fazer algumas perguntas, serão {N} perguntas "
                        "no total."
                    )
                )
                return send_survey(update, context)
            else:
                update.message.reply_text(
                    (
                        f"Olá, {update.message.from_user.first_name}, você "
                        f"já respondeu o questionário do @{bot_name}. Se você "
                        "deseja refazê-lo clique no botão abaixo."
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Refazer",
                                    url=f"https://t.me/avaliacao_bot?start={bot_name}_v2",
                                )
                            ]
                        ]
                    ),
                )
        elif "_v2" in bot_name:
            bot_name, _ = bot_name.split("_")
            context.user_data["bot_name"] = bot_name
            context.user_data["current_survey"] = utils._SURVEYS[bot_name][
                "questions"
            ]
            context.user_data["question_id"] = 0
            update.message.reply_text(
                f"Okay, vamos refazer o questionário do @{bot_name}."
            )
            return send_survey(update, context)
        else:
            update.message.reply_text(
                "Nenhum survey encontrado com esse nome!"
            )
    else:
        update.message.reply_text(
            (
                "Olá, sou um bot de avaliação, para conversar comigo é "
                "necessário que o @bot_name te encaminhe até mim."
            )
        )


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


def button(update, context):
    query = update.callback_query
    poll = query.message.poll
    required = context.bot_data[poll.id]["required"]
    if (
        "has_answer" in context.bot_data[poll.id]
        and context.bot_data[poll.id]["has_answer"]
    ) or not required:
        query.answer()
        context.user_data["question_id"] = int(query.data)
        query.edit_message_reply_markup(reply_markup=None)
        send_survey(update, context)
        if poll:
            context.bot.stop_poll(
                context.bot_data[poll.id]["chat_id"],
                context.bot_data[poll.id]["message_id"],
            )
        if "has_answer" in context.bot_data[poll.id]:
            user_id = query.message.chat.id
            utils.save_answer(
                context.user_data["bot_name"],
                user_id,
                context.bot_data[poll.id]["question_id"],
                context.bot_data[poll.id]["answer_string"],
            )
    else:
        query.answer("Você deve informar pelo menos uma opção!")


def regular_answer(update, context):
    question_id = context.user_data["question_id"]
    context.user_data["question_id"] = question_id + 1
    current_survey = context.user_data["current_survey"]
    list_size = len(current_survey)
    if context.user_data["question_id"] > list_size:
        print("conversa finalizada!!")
        return ConversationHandler.END
    else:
        # utils.save_answer(bot_name, user_id, context.user_data['question_id']-1, answer_string)
        utils.save_answer(
            context.user_data["bot_name"],
            update.message.from_user.id,
            context.user_data["question_id"] - 1,
            update.message.text,
        )
        return send_survey(update, context)


def done(update, context):
    update.message.reply_text("Conversa finalizada!")
    return ConversationHandler.END


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text("Help!")


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    global connection, cursor
    connection, cursor = utils.database_connection()
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(os.getenv("TOKEN"), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    # dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(PollAnswerHandler(receive_poll_answer))
    dp.add_handler(CallbackQueryHandler(button))

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={NEXT: [MessageHandler(Filters.text, regular_answer)],},
        fallbacks=[MessageHandler(Filters.regex("^Done$"), done)],
    )

    dp.add_handler(conv_handler)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    utils.close_connection()


if __name__ == "__main__":
    main()
