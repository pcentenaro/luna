source .env
chmod 400 $KEY_PAIR_FILE
ssh -o ServerAliveInterval=30 -i $KEY_PAIR_FILE ubuntu@$EC2_PUBLIC_DNS