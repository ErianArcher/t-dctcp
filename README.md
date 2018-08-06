# T-DCTCP
Combine TIMELY with DCTCP
# How to use this algorithm
## Folder structure
    .
    ├── experiement
    |  ├── exp              # This folder contains all the experiment scripts
    |  ├── util             # This folder contains scripts for visualizing experiment results
    ├── docs                # The thesis of T-DCTCP and presentation PPT are in this folder
    ├── result              # A set of experiment result
    |  ├── parameter_value_comparison # Experiment result for choose good values for different parameters
    |  ├── parameters_proof.xlsx      # Drawing diagrams for the comparison of different values for different parameters and the comparison of throughput between DCTCP and T-DCTCP
    |  ├── ...
    ├── gen_bytes.py # It is used to generate data files for transmission test.
    ├── PostHTTPServer.py # It is neccessary for line 406 of experiment/exp/exp.py
    ├── depoly_dctcp.sh
    ├── depoly_tdctcp.sh
    ├── depoly.sh           # Probe modules to kernel
    └── tcp_tdctcp.c        # Source code of T-DCTCP algorithm
---
## Prerequisition
+ System Specifications: Best for **Ubuntu 16.04** or any system with **Linux kernel 4.13.0**.
+ I try to install my project on Mininet VM provided by official website, but it cannot run Fat-tree topology correctly because of out-of-date ovs-switch version.
+ This algorithm is only tested with Linux kernel 4.13.0-43-generic, and this kernel contains the implementation of DCTCP, from which I borrow the code of updating the value of alpha.
+ BWM-NG: `apt-get install bwm-ng`
+ Python: Matplotlib *(The VM cannot run Matplotlib for the module, `six`,  is not up-to-date)* and Termcolor. **They are used to plot the data from the result. (The commented codes in `experiment/exp/run-exp.sh`)**
``` shell
sudo python ../util/plot_tcpprobe.py -f $odir/tcp_probe.txt -o $odir
sudo python ../util/plot_bw.py -f $odir/iperf_h1.txt -o $odir
python ../util/plot_tcpprobe.py -f ./tdctcp-n16-bw100/tcp_probe.txt ./dctcp-n16-bw100/tcp_probe.txt ./tcp-n16-bw100/tcp_probe.txt -o comparison
python ../util/plot_fct.py -f ./tdctcp-n16-bw100/fct.txt ./dctcp-n16-bw100/fct.txt -o .
```

## Steps to run
```
1. Install Ryu and Hedera following the instruction in (https://github.com/Huangmachi/Hedera)
2. cd t-dctcp
3. chmod +x deploy.sh
4. sudo ./deploy.sh
5. cd experiment/exp
6. chmod +x run-exp.sh
7. Change the parameter, ryu_cmd, to the absolute location of Hedera.py on line 8 of run-exp.sh
8. mkdir comparison # Must be run before step 9 unless a folder named `comparison` has been created.
9. sudo ./run-exp.sh
```
*After the script finishes, three folders will appear in current directory, and they are the results of experiment. If Matplotlib is installed on your PC or VM, some diagrams revealing how T-DCTCP performs will be generated including throughput, flow completion time and round trip time.*
```shell
python ../util/plot_tcpprobe.py -f ./tdctcp-n16-bw100/tcp_probe.txt ./dctcp-n16-bw100/tcp_probe.txt ./tcp-n16-bw100/tcp_probe.txt -o comparison
```
**A folder, comparison, has to be generated before the code above is run. Only the file, CDF_RTT.png, is useful in this folder.**

---
# Implementation
Most of the code are from the source code of DCTCP, and I actually add some new functions, constant variables and modifications in structure. The behavior of `*(ssthresh)` is modified, and it will return the value of new cwnd calculated by my algorithm. This means TDCTCP follows the implementation logic of DCTCP, and it will not change the cwnd if the new cwnd should decrease, instead it convey the new cwnd to threshold and TCP will refer to this new cwnd when congestion occurs.

# Parameters
+ g: 1/16 *(EWMA weight parameter for calculating new alpha)*
+ alpha_factor: 1/8
+ beta: 1/8 *(EWMA weight parameter for calculating new rtt_diff)*
+ addstep: 1
+ multiplicative decrement factor: 1/4
+ decre: 1/2 (reduce the reduction)
+ THigh: 50000us *(100Mbps)* 5000us *(1Gbps)* 500us *(10Gbps)*
+ TLow: 5000us *(100Mbps)* 500us *(1Gbps)* 50us *(10Gbps)*
