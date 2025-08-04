FROM ubuntu:22.04

# Install systemd properly for containers
RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y \
      systemd \
      systemd-sysv \
      openssh-server \
      sudo && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Remove systemd services that don't work in containers
RUN find /etc/systemd/system \
         /lib/systemd/system \
         -path '*.wants/*' \
         \( -name '*getty*' -o -name '*systemd-networkd*' -o -name '*systemd-resolved*' -o -name '*udev*' \) \
         -exec rm \{} \;

RUN systemctl set-default multi-user.target

# Rest of your setup...
RUN useradd -m ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/ubuntu/.ssh
COPY authorized_keys /home/ubuntu/.ssh/authorized_keys
RUN chown -R ubuntu:ubuntu /home/ubuntu/.ssh && \
    chmod 700 /home/ubuntu/.ssh && \
    chmod 600 /home/ubuntu/.ssh/authorized_keys

RUN systemctl enable ssh

CMD ["/lib/systemd/systemd"]
