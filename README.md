# Luna

## 1. How to run the bot

To run the bot on Linux, you first need to install Python. To do so, run the following commands in the terminal:

```bash
sudo apt update
sudo apt install python3.12
```

With Python installed, go to the root directory of the repository and run

```bash
python3 -m venv venv
```

This will create a virtual environment directory called `venv`. This is very important, because it provides an isolated environment that allows you to install and configure packages specifically for this project. With the environment ready, run

```bash
source venv/bin/activate
```

This command will activate the virtual environment, which means that every time you run Python, and every time you install a package, your actions will only affect the project in the repository. To leave the environment, you can just type

```bash
deactivate
```

To install the requirements needed to make the bot work, run

```bash
pip install -r requirements.txt
```

`pip` is Python's official package manager. The `requirements.txt` file allows you to list multiple packages to be installed by `pip`, without having to list them in the command line.

Now the only thing left to do is configure your `.env` file. This file allows you to define variables that contain secret values that you don't want to reveal in your code. The `.env` file is included in `.gitignore`, so it's not pushed to the remote repository when you commit changes. So, for this next step, contact Void for the `.env` file, and then put it in the root of your local repository.