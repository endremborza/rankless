FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
# Create user, SSH, and sudo setup
# Install dependencies and set up SSH server
RUN apt update && \
     apt install -y --no-install-recommends \
        dbus \
        dbus-user-session \
        dbus-daemon \
        libdbus-1-3 \
        openssh-server \
        sudo \
        rsync \
        git \
        curl \
        nginx \
        certbot \
        python3-certbot-nginx && \    
    mkdir -p /var/run/sshd /etc/ssh && \
    ssh-keygen -A && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config || true && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config || true && \
    sed -i 's@session\\s\\+required\\s\\+pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd || true

# Create a user like EC2 and allow passwordless sudo
# RUN useradd -m -s /bin/bash ubuntu && \
    # echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN useradd -m -s /bin/bash ubuntu && \
    mkdir -p /home/ubuntu/.ssh && \
    chown ubuntu:ubuntu /home/ubuntu/.ssh && \
    chmod 700 /home/ubuntu/.ssh && \
    # echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
    # chmod 440 /etc/sudoers.d/ubuntu

# Add your public key to the ubuntu user
COPY authorized_keys /home/ubuntu/.ssh/authorized_keys
RUN chown -R ubuntu:ubuntu /home/ubuntu/.ssh && \
    chmod 700 /home/ubuntu/.ssh && \
    chmod 600 /home/ubuntu/.ssh/authorized_keys

# Optional: Copy dummy nginx config and SSL certs here for testing
# COPY test-nginx.conf /etc/nginx/sites-available/default
# COPY dummy-fullchain.pem /etc/letsencrypt/live/test.local/fullchain.pem
# COPY dummy-privkey.pem /etc/letsencrypt/live/test.local/privkey.pem

# Expose SSH and HTTP/HTTPS ports
EXPOSE 22 80 443

# Set up default XDG env so systemctl --user works
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

CMD ["/usr/local/bin/docker-entrypoint.sh"]
