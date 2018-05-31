# TDCTCP
Combine TIMELY with DCTCP
# How to use this algorithm
## Prerequisition
+ Mininet VM: download [Mininet 2.2.2 on Ubuntu 14.04 LTS - 32 bit](https://github.com/mininet/mininet/releases/download/2.2.2/mininet-2.2.2-170321-ubuntu-14.04.4-server-i386.zip) and follow the [user guide](http://mininet.org/download/#option-1-mininet-vm-installation-easy-recommended) to start the VM.
+ (Optional) You can also install Mininet on your local machine, but some errors may occur when compiling tcp_tdctcp, because Linux Kernel may be updated in some header files. **If you need a local Mininet, then you should fix the errors occurring by yourself while compilation fails.**
+ This algorithm is only tested with Linux Kernel 4.2.0-generic, and this kernel contains the implementation of DCTCP, from which I borrow the code of updating the value of alpha.
+ BWM-NG: `apt-get install bwm-ng`
+ Python: Matplotlib *(The VM cannot run Matplotlib for the module, `six`,  is not up-to-date)* and Termcolor. **They are used to plot the data from the result. (The commented codes in `experiment/exp/run-exp.sh`)**
``` shell
#sudo python ../util/plot_rate.py --maxy $bw -f $odir/txrate.txt -o $odir/rate.png
#sudo python ../util/plot_queue.py --maxy 50 -f $odir/qlen_s1-eth1.txt -o $odir/qlen.png
#sudo python ../util/plot_tcpprobe.py -f $odir/tcp_probe.txt -o $odir
```

## Steps to run
```
1. Copy the repository to the VM via ssh.
2. cd tdctcp
3. chmod +x deploy.sh
4. sudo ./deploy.sh
5. cd experiment/exp
6. chmod +x run-exp.sh
7. sudo ./run-exp.sh
```
*After the script finishes, some folders will appear in current directory, and they are the result of experiment. If Matplotlib is installed on your PC or VM, you can uncomment the commented codes in run-exp.sh as showed in last section, and some diagram will be generated which can directly show how the algorithm performs.*

---
# Implementation
Most of the code are from the source code of DCTCP, and I actually add some new functions, constant variables and modifications in structure. The behavior of `*(ssthresh)` is modified, and it will return the value of new cwnd calculated by my algorithm. This means TDCTCP follows the implementation logic of DCTCP, and it will not change the cwnd if the new cwnd should decrease, instead it convey the new cwnd to threshold and TCP will refer to this new cwnd when congestion occurs.

# Parameters
+ g: 1/16 *(EWMA weight parameter for calculating new alpha)*
+ alpha_factor: 1/8
+ beta: 1/8 *(EWMA weight parameter for calculating new rtt_diff)*
+ addstep: 2
+ multiplicative decrement factor: 1/4
+ decre: 1/2 (reduce the reduction)
+ THigh: 50000us *(100Mbps)* 5000us *(1Gbps)* 500us *(10Gbps)*
+ TLow: 5000us *(100Mbps)* 500us *(1Gbps)* 50us *(10Gbps)*