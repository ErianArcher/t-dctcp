#!/bin/bash

bws="100 1000"
bws="100"
t=20
n=16
maxq=425
ryu_cmd="/home/erian/Documents/graduation_design/ryu/ryu/app/Hedera/Hedera.py" # Location of hedera script

function tcp {
	bw=$1
	odir=tcp-n$n-bw$bw
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>/dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n
	sudo mn -c
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>/dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n --fct
	sudo mn -c
    #sudo python ../util/plot_rate.py --maxy $bw -f $odir/txrate.txt -o $odir/rate.png
	#sudo python ../util/plot_queue.py -f $odir/qlen_s1-eth1.txt -o $odir/qlen.png
	sudo python ../util/plot_tcpprobe.py -f $odir/tcp_probe.txt -o $odir
	sudo python ../util/plot_bw.py -f $odir/iperf_h1.txt -o $odir # Output throughput
}

function dctcp {
	bw=$1
	odir=dctcp-n$n-bw$bw
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n --dctcp
	sudo mn -c
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n --dctcp --fct
	sudo mn -c
	#sudo python ../util/plot_rate.py --maxy $bw -f $odir/txrate.txt -o $odir/rate.png
	#sudo python ../util/plot_queue.py --maxy 50 -f $odir/qlen_s1-eth1.txt -o $odir/qlen.png
	sudo python ../util/plot_tcpprobe.py -f $odir/tcp_probe.txt -o $odir
	sudo python ../util/plot_bw.py -f $odir/iperf_h1.txt -o $odir # Output throughput
}

function tdctcp {
	bw=$1
	odir=tdctcp-n$n-bw$bw
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n --tdctcp
	sudo mn -c
	ryu-manager --observe-links "$ryu_cmd" --k_paths=4 --weight=hop --fanout=4 1>dev/null 2>&1 &
	sudo python exp.py --bw $bw --maxq $maxq --dir $odir -t $t -n $n --tdctcp --fct
	sudo mn -c
	#sudo python ../util/plot_rate.py --maxy $bw -f $odir/txrate.txt -o $odir/rate.png
	#sudo python ../util/plot_queue.py --maxy 50 -f $odir/qlen_s1-eth1.txt -o $odir/qlen.png
	sudo python ../util/plot_tcpprobe.py -f $odir/tcp_probe.txt -o $odir 
	sudo python ../util/plot_bw.py -f $odir/iperf_h1.txt -o $odir # Output throughput
}

for bw in $bws; do
    tcp $bw
    dctcp $bw
	tdctcp $bw
	python ../util/plot_tcpprobe.py -f ./tdctcp-n16-bw100/tcp_probe.txt ./dctcp-n16-bw100/tcp_probe.txt ./tcp-n16-bw100/tcp_probe.txt -o comparison
	python ../util/plot_fct.py -f ./tdctcp-n16-bw100/fct.txt ./dctcp-n16-bw100/fct.txt -o .
done
