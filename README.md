# Luna

## 1. How to run the bot locally

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

## 2. How to connect to AWS

You can connect to the AWS EC2 instance using the `connect_ec2.sh` script in the root of the repository. Before you run it, you need a private key pair. Key pairs are files containing hash codes that tell the EC2 instance that you are allowed to connect to them. Key pairs should remain a secret, just like the `.env` file; which is why they are registered in `gitignore` as `*.pem`. To receive a key pair, contact Void. Place the key pair in the root of the repository, then add the following lines to your `.env` file:

```bash
EC2_PUBLIC_DNS="[ec2-instance-dns]"
KEY_PAIR_FILE="[your-key-pair-file.pem]"
```

Contact Void if you need to know the EC2 instance's public DNS.

In the root of the repository, run this command:

```bash
chmod +x connect_ec2.sh
```

This will allow you to run the connection script, which you can do by typing this:

```bash
./connect_ec2.sh
```

If done correctly, you will receive access to the EC2 instance, which you can then manipulate locally. For all further connections, you just have to run the command above. To disconnect from the EC2 instance, run the command:

```bash
exit
```

## 3. Running the bot in the EC2 instance

If the bot is not running in AWS, you can start it by running the following commands:

```bash
source [path/to/repo/root/venv/bin/activate]
nohup python3 [path/to/main.py] >luna.log 2>&1 &
```

This runs the main script within the EC2 instance. The `&` at the end of the command tells the terminal to run it in the background, so you can resume your activities after starting the bot. The `nohup` command launches the Python process with persistency settings, which means that the script will keep running even after you disconnect from the instance. `>luna.log 2>&1` ensures that the process keeps running after the SSH session is closed by redirecting the program's standard output to a file, instead of keeping it connected to the SSH session. It also reroutes `stderr` to `stdout`, effectively passing error messages to `luna.log` as well.

If you need to stop the bot from running, you have to locate its process ID (PID). Run this command:

```bash
ps aux | grep "python3"
```

Here, `ps aux` lists all the running processes. The output of this command is passed to `grep`, which filters all the processes containing the term `python3`. Locate the line containing `python3 [path/to/main.py]`, get the PID, and run the following command to stop the bot:

```bash
kill [PID]
```
