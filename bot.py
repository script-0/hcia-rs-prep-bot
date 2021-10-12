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
CLOSED_QUIZ_MSG = (
    "Sorry ! Your Quiz section is closed. Please send /quiz to start a new one"
)
OLD_QUIZ_MSG = (
    "Sorry ! Your Quiz section is too old. Please send /quiz to start a new one"
)
NO_PREVIOUS_POLL_MSG = (
    "Sorry ! No previous quiz session found. Plz send /quiz to start a new one."
)
BAD_POLL_TYPE = "Sorry ! Only quiz polls are supported. Make sure to select quiz when building your Poll"
QUIZ_SAVED = "All done, Great ! Quiz saved succesfully."
QUIZ_UPDATE = "All done, Great ! Quiz updated successfully."
QUIZ_PER_SESSION = 5
SECOND_PER_QUIZ = 20
NO_PREVIOUS_POLL = -1


""" Setup Logging """
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> None:
    """Inform user about what this bot can do"""
    update.message.reply_photo(
        photo=open("hcia_rs_files_tmp/logo.png", "rb"),
        caption="Please select /poll to get a Poll, /quiz to get a Quiz or /preview to generate a preview for your poll",
    )


def poll(update: Update, context: CallbackContext) -> None:
    """Sends a predefined poll"""
    questions = ["Good", "Really good", "Fantastic", "Great"]
    message = context.bot.send_poll(
        update.effective_chat.id,
        "How are you?",
        questions,
        is_anonymous=False,
        allows_multiple_answers=True,
    )
    # Save some info about the poll the bot_data for later use in receive_poll_answer
    payload = {
        message.poll.id: {
            "questions": questions,
            "message_id": message.message_id,
            "chat_id": update.effective_chat.id,
            "answers": 0,
        }
    }
    context.bot_data.update(payload)


def receive_poll_answer(update: Update, context: CallbackContext) -> None:
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    try:
        questions = context.bot_data[poll_id]["questions"]
    # this means this poll answer update is from an old poll, we can't do our answering then
    except KeyError:
        return
    selected_options = answer.option_ids
    answer_string = ""
    for question_id in selected_options:
        if question_id != selected_options[-1]:
            answer_string += questions[question_id] + " and "
        else:
            answer_string += questions[question_id]
    context.bot.send_message(
        context.bot_data[poll_id]["chat_id"],
        f"{update.effective_user.mention_html()} feels {answer_string}!",
        parse_mode=ParseMode.HTML,
    )
    context.bot_data[poll_id]["answers"] += 1
    # Close poll after three participants voted
    if context.bot_data[poll_id]["answers"] == 3:
        context.bot.stop_poll(
            context.bot_data[poll_id]["chat_id"],
            context.bot_data[poll_id]["message_id"],
        )


def quiz(update: Update, context: CallbackContext) -> None:
    """Send a predefined poll"""
    questions = ["1", "2", "4", "20"]

    message = update.effective_message.reply_poll(
        "How many eggs do you need for a cake?",
        questions,
        type=Poll.QUIZ,
        correct_option_id=2,
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


def get_latest_poll_id(bot_data):
    tmp = list(bot_data.keys())
    return tmp[-1] if len(tmp) > 0 else NO_PREVIOUS_POLL


def clear_data(bot_data):
    for i in list(bot_data.keys()):
        del bot_data[i]


def next_question(update: Update, context: CallbackContext) -> None:
    previous_poll_id = get_latest_poll_id(context.bot_data)

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
        # Send Another quiz
        questions = ["1", "2", "4", "20"]
        message = context.bot.send_poll(
            chat_id=quiz_data["chat_id"],
            question="How many eggs do you need for a cake? - "
            + str(nb_question % QUIZ_PER_SESSION),
            options=questions,
            type=Poll.QUIZ,
            correct_option_id=(nb_question % QUIZ_PER_SESSION),
            open_period=SECOND_PER_QUIZ,
        )
        # Save some info about the poll the bot_data for later use in receive_quiz_answer\
        quiz_data["message_id"] = message.message_id
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


def preview(update: Update, context: CallbackContext) -> None:
    """Ask user to create a poll and display a preview of it"""
    # using this without a type lets the user chooses what he wants (quiz or poll)
    button = [[KeyboardButton("Press me!", request_poll=KeyboardButtonPollType())]]
    message = "Press the button to let the bot generate a preview for your poll"
    # using one_time_keyboard to hide the keyboard
    update.effective_message.reply_text(
        message, reply_markup=ReplyKeyboardMarkup(button, one_time_keyboard=True)
    )


def load_quiz(chat_id: int, msg_id: int, del_id = False) -> dict :
    quiz = dict()
    try:
        logger.info("[i]-> Search in load_quiz(...) -> [ chat = " + str(chat_id) + " , msg = " + str(msg_id) + " ]")
        quiz = mongoClient.hcia.quiz.find_one({
            "chat_id" : chat_id,
            "msg_id" : msg_id
        })
    except Exception as ex:
        logger.error("-> Exception in load_quiz(...) -> [ chat = " + str(chat_id) + " , msg = " + str(msg_id) + " ] -> "+ str(ex))
        return None
    
    if( del_id and ("_id" in list(quiz.keys())) ):
        del quiz["_id"]
    return quiz

def receive_poll(update: Update, context: CallbackContext) -> None:
    """On receiving polls, reply to it by a closed poll copying the received poll"""

    previous_poll = dict()
    # If reply to a poll == Poll modification
    try:
        replied_poll = update.effective_message.reply_to_message
        previous_poll['msg_id'] = replied_poll.message_id
        previous_poll['chat_id'] = replied_poll.chat.id
        previous_poll = load_quiz(chat_id=previous_poll['chat_id'] , msg_id=previous_poll['msg_id'])
    except Exception as ex:
        print("Loaded Poll : \n" + str(previous_poll) + " ->  Exception : " + str(ex))
        pass

    # If an image
    try:
        # If reply to a poll
        print("Loaded Poll : \n" + str(previous_poll))
        if "msg_id" in list(previous_poll.keys()):
            actual_photo = update.effective_message.photo
            photos = [ tmp_photo.file_unique_id for tmp_photo in actual_photo]
            previous_poll['imgs'] = photos
            mongoClient.hcia.quiz.replace_one(previous_poll)
        else:
            update.effective_message.reply_text('Please select a Poll. Reply to  a poll')
        return
    except Exception as ex:
        print("Saved Poll : \n" + str(previous_poll) + " ->  Exception : " + str(ex))
        pass
    
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
        quiz['_id'] = previous_poll['_id']
        quiz['msg_id'] = previous_poll['msg_id']
        quiz['chat_id'] = previous_poll['chat_id']
        mongoClient.hcia.quiz.replace_one({"_id" : quiz["_id"]},quiz)
    else :
        # Save quiz
        mongoClient.hcia.quiz.insert_one(quiz)

    update.effective_message.reply_poll(
        question=actual_poll.question,
        options=[o.text for o in actual_poll.options],
        # with is_closed true, the poll/quiz is immediately closed
        is_closed=True,
        reply_markup=ReplyKeyboardRemove(),
    )

    update.effective_message.reply_text( QUIZ_UPDATE if "msg_id" in list(previous_poll.keys()) else QUIZ_SAVED)


def help_handler(update: Update, context: CallbackContext) -> None:
    """Display a help message"""
    update.message.reply_text("Use /quiz, /poll or /preview to test this bot.")


def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("next", next_question))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("poll", poll))
    dispatcher.add_handler(PollAnswerHandler(receive_poll_answer))
    dispatcher.add_handler(CommandHandler("quiz", quiz))
    dispatcher.add_handler(PollHandler(receive_quiz_answer))
    dispatcher.add_handler(CommandHandler("preview", preview))
    dispatcher.add_handler(MessageHandler(Filters.poll, receive_poll))
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

    #updater.start_webhook(
    #    listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=APP_NAME + TOKEN
    #)
    # Start the Bot

    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]
    updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == "__main__":
    main()
