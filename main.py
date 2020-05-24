import utils

import os
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAnimation,
    InputMediaVideo,
    InputMediaPhoto
)

from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    PollAnswerHandler,
    CallbackQueryHandler,
)

from telegram.utils import helpers


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO,
)

logger = logging.getLogger(__name__)

CLOSED, OPEN, REGULAR_ANSWER = range(3)


def send_question(update, context):
    next_question = "survey_finish"
    question_id = context.user_data["question_id"]
    current_survey = context.user_data["current_survey"]
    list_size = len(current_survey)

    button_text = "⏭️ Próxima"

    callback_data = next_question
    if question_id + 1 < list_size:
        if len(current_survey[question_id + 1]["options"]) > 1:
            next_question = "closed"
        else:
            next_question = "open"
        callback_data = f"{next_question}_{question_id + 1}"

    if next_question == "survey_finish":
        button_text = "✅ Finalizar!"

    keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message and not update.message.text.startswith("/start"):
        bot_message = update.message.reply_text(
            f"Sua resposta: {update.message.text}", reply_markup=reply_markup
        )
        context.user_data[update.message.message_id] = bot_message.message_id
        context.user_data[bot_message.message_id] = reply_markup
        context.user_data["regular_answers"][update.message.message_id] = [
            question_id,
            update.message.text,
        ]
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
                    "open": True,
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
        repeat = None
        if bot_name.startswith("repeat-"):
            repeat, bot_name = bot_name.split("-")
        if bot_name in utils._SURVEYS:
            #  Checar se o usuário já respondeu este survey
            if not utils.is_answered(update.message.from_user.id, bot_name) or repeat:
                context.user_data["regular_answers"] = {}
                context.user_data["polls"] = []
                context.user_data["question_id"] = 0
                context.user_data["bot_name"] = bot_name
                context.user_data["current_survey"] = utils._SURVEYS[bot_name]["questions"]
                N = len(utils._SURVEYS[bot_name]["questions"])
                update.message.reply_text(
                    (
                        f"Olá, {update.message.from_user.first_name}, o bot "
                        f"@iqa_imdbot te encaminhou para que possa avaliá-lo. Eu "
                        f"irei lhe fazer algumas perguntas, serão {N} perguntas "
                        "no total."
                    )
                )
                # enviar primeira pergunta
                answer_type = send_question(update, context)
                if context.user_data["current_survey"][0]["options"]:
                    if answer_type == "closed":
                        return CLOSED
                    elif answer_type == "open":
                        return OPEN
                else:
                    return REGULAR_ANSWER
            else:
                url = helpers.create_deep_linked_url(context.bot.get_me().username, "repeat-imdbot")
                keyboard = InlineKeyboardMarkup.from_button(
                    InlineKeyboardButton(text='Refazer!', url=url)
                )
                update.message.reply_text(
                    "Você já respondeu esse questionário, se desejar refazê-lo clique no botão abaixo.",
                    reply_markup = keyboard
                    )
        else:
            update.message.reply_text("Nenhum questionário encontrado com este nome.")
    else:
        update.message.reply_text("Você não pode começar uma conversa com esse bot, é necessário o @iqa_imdbot redirecionar você.")


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
    if answer_type == "open":
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
    if answer_type == "open":
        return OPEN
    else:
        return CLOSED


def end(update, context):
    query = update.callback_query
    finished = True
    # Encerrar todas as polls da conversa:
    for poll_id in context.user_data["polls"]:
        required = context.bot_data[poll_id]["required"]
        if (
            "has_answer" in context.bot_data[poll_id]
            and context.bot_data[poll_id]["has_answer"]
        ) or not required:
            if context.bot_data[poll_id]["open"]:
                context.bot_data[poll_id]["open"] = False
                context.bot.stop_poll(
                    context.bot_data[poll_id]["chat_id"],
                    context.bot_data[poll_id]["message_id"],
                )
                if "has_answer" in context.bot_data[poll_id]:
                    print(context.bot_data[poll_id]["answer_string"])
                    user_id = query.message.chat.id
                    utils.save_answer(
                        context.user_data["bot_name"],
                        user_id,
                        context.bot_data[poll_id]["question_id"],
                        context.bot_data[poll_id]["answer_string"],
                    )
        else:
            finished = False
            query.answer("Campos obrigatórios não preenchidos!")
    if finished:
        query.answer()
        query.edit_message_reply_markup(None)

        for _, values in context.user_data["regular_answers"].items():
            question_id, answer_string = values[0], values[1]
            print(question_id, answer_string)
            user_id = query.message.chat.id
            utils.save_answer(
                context.user_data["bot_name"],
                user_id,
                question_id,
                answer_string,
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
        context.bot.edit_message_text(
            chat_id=update.edited_message.chat.id,
            message_id=message_bot_id,
            text=f"Sua resposta: {update.edited_message.text}",
            reply_markup=reply_markup,
        )
        # Atualizar resposta do usuário:
        context.user_data["regular_answers"][message_id][1] = update.edited_message.text


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


def help_button(update, context):
    query = update.callback_query
    query.answer()
    _, hid = query.data.split("_")
    hid = int(hid)

    keyboard = [[]]
    next_button = InlineKeyboardButton("próximo", callback_data=f"help_{hid+1}")
    prev_button = InlineKeyboardButton("anterior", callback_data=f"help_{hid-1}")
    media = None
    if hid == 0:
        caption = ("Há três tipos de perguntas no bot, sendo elas:\n\n"
            "▪️ *múltiplas escolhas*\n▪️ *única escolha*\n▪️ *texto livre*.\n\nTodas "
            "as respostas _são editáveis antes da finalização_ do questionário."
        )
        media = InputMediaAnimation(
                "CgACAgEAAxkBAAIDz165k3F3dOyCpA0NzXKTkbk2RT_rAAKfAAPJItBFxyufgHgzykAZBA",
                caption=caption,
                parse_mode="markdown"
            )
        keyboard[0].append(next_button)
    elif hid == 1:
        caption = ("As perguntas podem ser obrigatórias ou opcionais, as "
            "*obrigatórias estão marcadas com estrela*."
        )
        media = InputMediaPhoto(
                "AgACAgEAAxkBAAIDjF65gy5cp6uTnlUBypOFFJ-dDw5mAAJRqDEbySLQRQ8xPAq4fpQp371uBgAEAQADAgADeAADe5kCAAEZBA",
                caption=caption,
                parse_mode="markdown"
            )
        keyboard[0].append(prev_button)
        keyboard[0].append(next_button)
    elif hid == 2:
        media = InputMediaVideo(
                "BAACAgEAAxkBAAIDfF65f7no-7Wmzex-mYwXmgR-EGuZAAIpAQACvlPJRVufPM2G1aFZGQQ",
                caption="Vídeo demonstrativo de como utilizar o bot.",
                parse_mode="markdown"
        )
        keyboard[0].append(prev_button)

    if media:
        context.bot.edit_message_media(
                query.message.chat.id,
                query.message.message_id,
                media=media,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )


def help(update, context):
    """Send a message when the command /help is issued."""
    keyboard = [
        [
            InlineKeyboardButton("próximo", callback_data="help_1"), 
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_animation(
            "CgACAgEAAxkBAAIDz165k3F3dOyCpA0NzXKTkbk2RT_rAAKfAAPJItBFxyufgHgzykAZBA",
            #open('tipos.gif', 'rb'),
            caption=("Há três tipos de perguntas no bot, sendo elas:\n\n"
            "▪️ *múltiplas escolhas*\n▪️ *única escolha*\n▪️ *texto livre*.\n\nTodas "
            "as respostas _são editáveis antes da finalização_ do questionário."),
            reply_markup=reply_markup,
            parse_mode="markdown",
    )


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(os.getenv("TOKEN"), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(PollAnswerHandler(receive_poll_answer))
    dp.add_handler(CallbackQueryHandler(help_button, pattern="^help_[0-9]$"))

    # Setup conversation handler with the states FIRST and SECOND
    # Use the pattern parameter to pass CallbackQueries with specific
    # data pattern to the corresponding handlers.
    # ^ means "start of line/string"
    # $ means "end of line/string"
    # So ^ABC$ will only allow 'ABC'
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CLOSED: [
                CallbackQueryHandler(question_with_options, pattern="^closed_[0-9]+$"),
                CallbackQueryHandler(end, pattern="^survey_finish$"),
            ],
            OPEN: [
                CallbackQueryHandler(question_without_options, pattern="^open_[0-9]+$"),
            ],
            REGULAR_ANSWER: [
                MessageHandler(Filters.regex("^(?!/).*"), regular_answer),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(Filters.regex("^(?!/).*"), edited),
        ],
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


if __name__ == "__main__":
    main()
