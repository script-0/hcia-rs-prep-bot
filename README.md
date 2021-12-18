# hcia-rs-prep-bot
A Telegram bot for question/answers relatively to HCIA R&amp;S Certification

[![Lint](https://github.com/script-0/hcia-rs-prep-bot/actions/workflows/lint.yml/badge.svg)](https://github.com/script-0/hcia-rs-prep-bot/actions/workflows/lint.yml)     [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## To DO

- [x] Implement interaction with user
- [x] User created quizz recording 
- [x] Integrate document based database (MongoDB Atlas)
- [x] Think about question with image : ADD illustration to Quiz
- [x] Remove illustration from QUIZ
- [ ] Auto complete feature on typing request
- [ ] More beautiful report
- [ ] More useful How to deploy
- [ ] Code refactoring

## How to deploy Locally

- Requirements

    - Python 3.7 or earlier
    - virtualenv
        ```bash
        $ pip3 install virtualenv
        ```
    - Initialised Bot with [@BotFather](https://t.me/BotFather)
- Code the repo
    ```bash
    $ git clone git@github.com:script-0/hcia-rs-prep-bot
    cd hcia-rs-prep
    ```

- Configure virtual environment

    ```bash
    $ virtualenv  venv -p python3
    source venv/bin/activate
    ```

- Install librairies
    ```bash
    $ pip3 install -r requirements.txt
    ```
- Define environment variables.
    ```bash
    $ export BOT_SECRET="YOUR_BOT_SECRET"
    $ export MONGO_DB="YOUR_MONGO_DB_URI" # format: "mongodb+srv://USERNAME:PASSWORD@cluster0.0soh0.mongodb.net/COLLECTION_NAME?retryWrites=true&w=majority"
    $ export USER_CODE="USER_CODE_TO_CREATE_QUIZ"
    ```

- Oooffs, Run it
    ```bash
    $ python3 bot.py
    ```

