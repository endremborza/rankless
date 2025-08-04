# VM configuration
VM_NAME=testvm
VM_PORT=2223
MEMORY=4096
CPUS=4
IMAGE=base.img
DISK=$(VM_NAME).qcow2
SEED=seed.iso

# SSH config
SSH_USER=ubuntu
SSH_OPTS=-o StrictHostKeyChecking=no -p $(VM_PORT)
SSH=ssh $(SSH_OPTS) $(SSH_USER)@localhost

# Default target
.PHONY: all
all: run

# Generate cloud-init seed with a fresh instance ID
$(SEED): user-data
	echo "instance-id: $(VM_NAME)-$$(uuidgen)" > meta-data
	cloud-localds $(SEED) user-data meta-data

# Create a new disk for this run
$(DISK): $(IMAGE)
	cp $(IMAGE) $(DISK)

# Run the VM
.PHONY: run
run: $(SEED) $(DISK) base.img
	qemu-system-x86_64 \
		-enable-kvm \
		-m $(MEMORY) -smp $(CPUS) \
		-drive file=$(DISK),format=qcow2 \
		-drive file=$(SEED),format=raw \
		-netdev user,id=net0,hostfwd=tcp::$(VM_PORT)-:22 \
		-device virtio-net-pci,netdev=net0 \
		-nographic

# SSH into the VM
.PHONY: ssh
ssh:
	$(SSH)

# Clean everything except base image and configs
.PHONY: clean
clean:
	@echo "Cleaning VM disk and seed ISO..."
	rm -f $(DISK) $(SEED) meta-data

jammy-server-cloudimg-amd64.img:
	wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

base.img: jammy-server-cloudimg-amd64.img
	cp jammy-server-cloudimg-amd64.img base.img
	qemu-img resize base.img 10G
