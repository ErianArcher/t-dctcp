TARGET = tcp_tdctcp
KDIR = /lib/modules/$(shell uname -r)/build
PWD = $(shell pwd)
obj-m := $(TARGET).o
default:
	make -C $(KDIR) M=$(PWD) modules
clean:
	$(RM) *.o *.ko *.mod.c Module.symvers

