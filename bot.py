#!/usr/bin/env python
# pylint: disable=C0116,W0613

import logging
import os
from telegram import (
    Poll,
    ParseMode,
    KeyboardButton,
    KeyboardButtonPollType,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    PollAnswerHandler,
    PollHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)
from telegram.files.photosize import PhotoSize

from models.quiz import Quiz

from telegram.constants import POLL_QUIZ

from look import track_chats, show_chats, greet_chat_members

# Additionnal imports need for previous functions
from typing import Tuple, Optional

from telegram import Chat, ChatMember, ChatMemberUpdated

from telegram.ext import ChatMemberHandler

from pymongo import MongoClient  # this lets us connect to MongoDB

""" Environment variables"""
mongoClient = MongoClient(os.environ.get("MONGO_DB"))
APP_NAME = "https://buzzvb.herokuapp.com/"
PORT = int(os.environ.get("PORT", "8443"))
# Don't forget to set Config Vars on Heroku (settings Section)
TOKEN = os.environ.get("BOT_SECRET")
LOGO_RELATIVE_PATH = "hcia_rs_files_tmp/logo.jpg"
HELLO_MESSAGE = "Hi, Nice to meet you! \n [->] /quiz to start a Q/A session. \n [->] /create to contribute to the Quiz librairy."
CLOSED_QUIZ_MSG = (
    "Sorry ! Your Quiz section is closed. Please send /quiz to start a new one."
)
OLD_QUIZ_MSG = (
    "Sorry ! Your Quiz section is too old. Please send /quiz to start a new one."
)
NO_PREVIOUS_POLL_MSG = (
    "Sorry ! No previous quiz session found. Plz send /quiz to start a new one."
)
BAD_POLL_TYPE = "Sorry ! Only quiz polls are supported. Make sure to select quiz when building your Poll."
QUIZ_SAVED = "All done, Great ! Quiz saved succesfully.\nIf your want to edit it or add image just reply to it."
QUIZ_UPDATE = "All done, Great ! Quiz updated successfully."
QUIZ_UPDATE_ADD_IMAGE = "All done, Great ! Illustration added successfully."
QUIZ_PER_SESSION = 10
SECOND_PER_QUIZ = 20
NO_PREVIOUS_POLL = -1
INITIALISE_QUIZ_MSG = "Press the above button to initialise Quiz Creation."
REPLIED_QUIZ_NOT_FOUND = "Sorry, the quiz you want to edit not found. Plz, make sure you selected the right one or try to create another one."
QUIZ_NOT_SELECTED = "Plz reply to a quiz."

""" Setup Logging """
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_quiz(quiz_to_skip=None):
    if quiz_to_skip == None:
        quiz = list(mongoClient.hcia.quiz.aggregate([{"$sample": {"size": 1}}]))[0]
        return quiz

    quiz = list(
        mongoClient.hcia.quiz.aggregate(
            [
                {"$match": {"_id": {"$not": {"$in": quiz_to_skip}}}},
                {"$sample": {"size": 1}},
            ]
        )
    )[0]

    return quiz


def start(update: Update, context: CallbackContext) -> None:
    """Inform user about what this bot can do"""
    update.message.reply_photo(
        photo=open(LOGO_RELATIVE_PATH, "rb"), caption=HELLO_MESSAGE
    )
    clear_data(context.bot_data)


def quiz(update: Update, context: CallbackContext) -> None:

    """Initiate Q/A session and send the first quiz"""
    # Clear al previous Q/A session data
    clear_data(context.bot_data)

    # Load a quiz
    quiz = get_quiz()

    # Send first quiz

    if('imgs' in list(quiz.keys())):
        update.effective_message.reply_photo(
            photo=quiz['imgs'][0]
        )
    
    message = update.effective_message.reply_poll(
        quiz["question"],
        quiz["options"],
        type=Poll.QUIZ,
        correct_option_id=int(quiz["response_id"]),
        # 5s to response
        open_period=SECOND_PER_QUIZ,
        # close_date=SECOND_PER_QUIZ
    )

    # Save some info about the poll the bot_data for later use in receive_quiz_answer
    payload = {
        message.poll.id: {
            "chat_id": update.effective_chat.id,
            "message_id": message.message_id,
            "nb_question": 0,
            "marks": 0,
            "quiz_to_skip": [quiz["_id"]],
        }
    }
    context.bot_data.update(payload)


def is_answer_correct(update):
    """determine if user answer is correct"""
    answers = update.poll.options
    ret = False
    counter = 0
    for answer in answers:
        if answer.voter_count == 1 and update.poll.correct_option_id == counter:
            ret = True
            break
        counter = counter + 1
    return ret


def get_latest_quiz_id(bot_data):
    tmp = list(bot_data.keys())
    return tmp[-1] if len(tmp) > 0 else NO_PREVIOUS_POLL


def clear_data(bot_data):
    for i in list(bot_data.keys()):
        del bot_data[i]


def next_question(update: Update, context: CallbackContext) -> None:
    previous_poll_id = get_latest_quiz_id(context.bot_data)

    if previous_poll_id == NO_PREVIOUS_POLL:
        update.effective_message.reply_text(NO_PREVIOUS_POLL_MSG)
        return
    quiz_data = context.bot_data[previous_poll_id]
    nb_question = quiz_data["nb_question"]

    # Stop current Quiz
    try:
        context.bot.stop_poll(quiz_data["chat_id"], quiz_data["message_id"])
    except Exception:
        pass

    if (nb_question + 1) < QUIZ_PER_SESSION:
        quiz_data["nb_question"] = quiz_data["nb_question"] + 1

        # Load previous quiz _id. This will be skipped
        quiz_to_skip = quiz_data["quiz_to_skip"]

        # Load another quiz
        quiz = get_quiz(quiz_to_skip)
        quiz_to_skip.append(quiz["_id"])

        # Send Another quiz
        if('imgs' in list(quiz.keys())):
            context.bot.send_photo(
                chat_id=quiz_data["chat_id"],
                photo=quiz['imgs'][0]
            )

        message = context.bot.send_poll(
            chat_id=quiz_data["chat_id"],
            question=quiz["question"] + str(nb_question % QUIZ_PER_SESSION),
            options=quiz["options"],
            type=Poll.QUIZ,
            correct_option_id=int(quiz["response_id"]),
            open_period=SECOND_PER_QUIZ,
        )
        # Save some info about the poll the bot_data for later use in receive_quiz_answer\
        quiz_data["message_id"] = message.message_id
        quiz_data["quiz_to_skip"] = quiz_to_skip

        payload = {message.poll.id: quiz_data}
        context.bot_data.update(payload)
    else:
        if quiz_data["marks"] >= 0.8 * QUIZ_PER_SESSION:
            context.bot.send_message(
                quiz_data["chat_id"],
                "WHOOWW, Great Work ! You got "
                + str(quiz_data["marks"])
                + " over "
                + str(QUIZ_PER_SESSION)
                + " -> "
                + str(round(quiz_data["marks"] * 100 / QUIZ_PER_SESSION))
                + "%",
            )
        else:
            context.bot.send_message(
                quiz_data["chat_id"],
                "Sorry, Need more work ! You got "
                + str(quiz_data["marks"])
                + " over "
                + str(QUIZ_PER_SESSION)
                + " -> "
                + str(round(quiz_data["marks"] * 100 / QUIZ_PER_SESSION))
                + "%",
            )
        clear_data(context.bot_data)


def receive_quiz_answer(update: Update, context: CallbackContext) -> None:
    """Respond after quiz user response"""
    try:
        # if not previous context data found , ignore
        if len(list(context.bot_data.keys())) <= 0:
            return
        # When the poll is closed after respond , ignore
        if update.poll.is_closed and (
            update.poll.id != list(context.bot_data.keys())[-1]
        ):
            return

        # calcul les points
        quiz_data = context.bot_data[update.poll.id]
        mark = is_answer_correct(update=update)
        quiz_data["marks"] += 1 if mark else 0
        payload = {update.poll.id: quiz_data}
        context.bot_data.update(payload)

        # Load next question
        next_question(update=update, context=context)

    except KeyError:
        # this means this poll answer update is from an old poll, we can't stop it then
        update.effective_message.reply_text(OLD_QUIZ_MSG)
        return


def init_quiz_creation(update: Update, context: CallbackContext) -> None:
    """Ask user to create a quiz and display"""

    # type=POLL_QUIZ : just QUIZ poll allowed
    button = [
        [KeyboardButton("Create", request_poll=KeyboardButtonPollType(type=POLL_QUIZ))]
    ]
    message = INITIALISE_QUIZ_MSG
    # using one_time_keyboard to hide the keyboard
    update.effective_message.reply_text(
        message, reply_markup=ReplyKeyboardMarkup(button, one_time_keyboard=True)
    )


def load_quiz(chat_id: int, msg_id: int, del_id=False) -> dict:
    quiz = dict()
    try:
        # logger.info("[i]-> Search in load_quiz(...) -> [ chat = " + str(chat_id) + " , msg = " + str(msg_id) + " ]")
        quiz = mongoClient.hcia.quiz.find_one({"chat_id": chat_id, "msg_id": msg_id})
    except Exception as ex:
        logger.error(
            "[e]-> Exception in load_quiz(...) -> [ chat = "
            + str(chat_id)
            + " , msg = "
            + str(msg_id)
            + " ] -> "
            + str(ex)
        )
        return None

    if del_id and ("_id" in list(quiz.keys())):
        del quiz["_id"]
    return quiz


def create_update_quiz(update: Update, context: CallbackContext) -> None:
    """On receiving polls, reply by a closed poll copying the received poll"""

    previous_poll = dict()

    replied_poll = update.effective_message.reply_to_message
    if replied_poll:
        # If reply to something
        if replied_poll.poll:
            # If reply to a poll == Poll modification
            previous_poll["msg_id"] = replied_poll.message_id
            previous_poll["chat_id"] = replied_poll.chat.id
            previous_poll = load_quiz(
                chat_id=previous_poll["chat_id"], msg_id=previous_poll["msg_id"]
            )
            if not previous_poll:
                # If error occured on quiz loading
                logger.error(
                    "[e]-> Exception in receive_poll() -> Loaded Poll : \n"
                    + str(previous_poll)
                )
                update.effective_message.reply_text(
                    REPLIED_QUIZ_NOT_FOUND,
                    reply_to_message_id=update.effective_message.message_id,
                )
                return
        else:
            update.effective_message.reply_text(
                QUIZ_NOT_SELECTED,
                reply_to_message_id=update.effective_message.message_id,
            )
            return

    actual_photo = update.effective_message.photo
    if actual_photo:
        # If an image
        try:
            # If reply to a poll
            if "msg_id" in list(previous_poll.keys()):
                photos = [tmp_photo.file_id for tmp_photo in actual_photo]
                previous_poll["imgs"] = photos
                mongoClient.hcia.quiz.replace_one(
                    {"_id": previous_poll["_id"]}, previous_poll
                )
                update.effective_message.reply_text(QUIZ_UPDATE_ADD_IMAGE)
            else:
                update.effective_message.reply_text(
                    QUIZ_NOT_SELECTED,
                    reply_to_message_id=update.effective_message.message_id,
                )
        except Exception as ex:
            logger.error(
                "[e]-> Saved Poll : \n"
                + str(previous_poll)
                + " ->  Exception : "
                + str(ex)
            )

        return

    actual_poll = update.effective_message.poll

    if actual_poll.type != POLL_QUIZ:
        # Not a quiz
        update.effective_message.reply_text(BAD_POLL_TYPE)
        return

    # Load quiz
    quiz = dict()
    quiz["question"] = actual_poll.question
    quiz["options"] = []
    for option in actual_poll.options:
        quiz["options"].append(option.text)
    quiz["response_id"] = actual_poll.correct_option_id
    quiz["explanation"] = actual_poll.explanation
    quiz["chat_id"] = update.effective_chat.id
    quiz["msg_id"] = update.effective_message.message_id

    # If reply to a poll
    if "msg_id" in list(previous_poll.keys()):
        quiz["_id"] = previous_poll["_id"]
        quiz["msg_id"] = previous_poll["msg_id"]
        quiz["chat_id"] = previous_poll["chat_id"]
        mongoClient.hcia.quiz.replace_one({"_id": quiz["_id"]}, quiz)
    else:
        # Save quiz
        mongoClient.hcia.quiz.insert_one(quiz)

    update.effective_message.reply_text(
        QUIZ_UPDATE if "msg_id" in list(previous_poll.keys()) else QUIZ_SAVED,
        reply_markup=ReplyKeyboardRemove(),
    )


def help_handler(update: Update, context: CallbackContext) -> None:
    """Display a help message"""
    update.message.reply_text("Use /quiz, /create to test this bot.")


def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("next", next_question))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("quiz", quiz))
    dispatcher.add_handler(PollHandler(receive_quiz_answer))
    dispatcher.add_handler(CommandHandler("create", init_quiz_creation))
    dispatcher.add_handler(MessageHandler(Filters.poll, create_update_quiz))
    dispatcher.add_handler(MessageHandler(Filters.photo, create_update_quiz))
    dispatcher.add_handler(CommandHandler("help", help_handler))

    # Keep track of which chats the bot is in
    dispatcher.add_handler(
        ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    dispatcher.add_handler(CommandHandler("look", show_chats))

    # Handle members joining/leaving chats.
    dispatcher.add_handler(
        ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER)
    )
    updater.start_webhook(
        listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=APP_NAME + TOKEN
    )
    # Start the Bot

    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]
    updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == "__main__":
    main()
