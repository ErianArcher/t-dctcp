#!/usr/bin/python
import sys
sys.path = ['../'] + sys.path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import lg
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import irange, custom, quietRun, dumpNetConnections
from mininet.cli import CLI
from mininet.node import Controller, RemoteController

from time import sleep, time
import multiprocessing
from subprocess import Popen, PIPE
import re
import argparse
import fattree4
from mininet.node import OVSKernelSwitch as Switch
import os
from os import path

import os
from util.monitor import monitor_cpu, monitor_qlen, monitor_devs_ng

parser = argparse.ArgumentParser(description="DCTCP tester (Star topology)")
parser.add_argument('--bw', '-B',
                    dest="bw",
                    action="store",
                    help="Bandwidth of links",
                    required=True)

parser.add_argument('--dir', '-d',
                    dest="dir",
                    action="store",
                    help="Directory to store outputs",
                    required=True)

parser.add_argument('-n',
                    dest="n",
                    action="store",
                    help="Number of nodes in star.  Must be >= 3",
                    required=True)

parser.add_argument('-t',
                    dest="t",
                    action="store",
                    help="Seconds to run the experiment",
                    default=30)

parser.add_argument('-u', '--udp',
                    dest="udp",
                    action="store_true",
                    help="Run UDP test",
                    default=False)

parser.add_argument('--use-hfsc',
                    dest="use_hfsc",
                    action="store_true",
                    help="Use HFSC qdisc",
                    default=False)

parser.add_argument('--maxq',
                    dest="maxq",
                    action="store",
                    help="Max buffer size of each interface",
                    default=400)

parser.add_argument('--speedup-bw',
                    dest="speedup_bw",
                    action="store",
                    help="Speedup bw for switch interfaces",
                    default=-1)

parser.add_argument('--dctcp',
                    dest="dctcp",
                    action="store_true",
                    help="Enable DCTCP (net.ipv4.tcp_congestion_control=dctcp)",
                    default=False)

parser.add_argument('--tdctcp',
                    dest="tdctcp",
                    action="store_true",
                    help="Enable TDCTCP (net.ipv4.tcp_congestion_control=tdctcp)",
                    default=False)

parser.add_argument('--reno',
                    dest="reno",
                    action="store_true",
                    help="Enable RENO (net.ipv4.tcp_congestion_control=reno)",
                    default=False)

parser.add_argument('--ecn',
                    dest="ecn",
                    action="store_true",
                    help="Enable ECN (net.ipv4.tcp_ecn=1)",
                    default=False)

parser.add_argument('--use-bridge',
                    dest="use_bridge",
                    action="store_true",
                    help="Use Linux Bridge as switch",
                    default=False)

parser.add_argument('--tcpdump',
                    dest="tcpdump",
                    action="store_true",
                    help="Run tcpdump on host interfaces",
                    default=False)

parser.add_argument('--fct',
                    dest="fct",
                    action="store_true",
                    help="Run fct test on host interfaces",
                    default=False)

parser.add_argument('--delay',
	dest="delay",
	default="0.075ms  0.05ms distribution normal  ")

args = parser.parse_args()
args.n = int(args.n)
args.bw = float(args.bw)
if args.bw > 101.0:
    args.delay = "0.005ms 0.005ms distribution normal"
if args.speedup_bw == -1:
    args.speedup_bw = args.bw
args.n = max(args.n, 2)

if not os.path.exists(args.dir):
    os.makedirs(args.dir)

lg.setLogLevel('info')

class StarTopo(Topo):

    def __init__(self, n=3, bw=100):
        # Add default members to class.
        super(StarTopo, self ).__init__()

        # Host and link configuration
        hconfig = {'cpu': -1}
	ldealay_config = {'bw': bw, 'delay': args.delay,
			'max_queue_size': 1000000
			} 
	lconfig = {'bw': bw, 
		   'max_queue_size': int(args.maxq),
		   'enable_ecn': args.ecn or args.dctcp or args.tdctcp,
           'use_hfsc' : args.use_hfsc,
           'speedup': float(args.speedup_bw)
           #'max_queue_size':1000
		}

        print '~~~~~~~~~~~~~~~~~> BW = %s' % bw

        # Create switch and host nodes
        for i in xrange(n):
            self.addHost('h%d' % (i+1), **hconfig)

        self.addSwitch('s1',)

        self.addLink('h1', 's1', **lconfig)
        for i in xrange(1, n):
            self.addLink('h%d' % (i+1), 's1', **ldealay_config)

def waitListening(client, server, port):
    "Wait until server is listening on port"
    if not 'telnet' in client.cmd('which telnet'):
        raise Exception('Could not find telnet')
    cmd = ('sh -c "echo A | telnet -e A %s %s"' %
           (server.IP(), port))
    while 'Connected' not in client.cmd(cmd):
        print 'Waiting for %s to listen on port %s\n'%(server, port)
        sleep(.5)

def progress(t):
    while t > 0:
        print '  %3d seconds left  \r' % (t)
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print '\r\n'

def enable_reno():
    Popen("sysctl -w net.ipv4.tcp_congestion_control=reno", shell=True).wait()

def enable_cubic():
    Popen("sysctl -w net.ipv4.tcp_congestion_control=cubic", shell=True).wait()

def enable_tcp_ecn():
    Popen("sysctl -w net.ipv4.tcp_ecn=1", shell=True).wait()

def disable_tcp_ecn():
    Popen("sysctl -w net.ipv4.tcp_ecn=0", shell=True).wait()

def enable_dctcp():
    Popen("sysctl -w net.ipv4.tcp_congestion_control=dctcp", shell=True).wait()
    enable_tcp_ecn()

def disable_dctcp():
    enable_cubic()
    disable_tcp_ecn()

def enable_tdctcp():
    Popen("sysctl -w net.ipv4.tcp_congestion_control=tdctcp", shell=True).wait()
    enable_tcp_ecn()

def disable_tdctcp():
    enable_cubic()
    disable_tcp_ecn()

def setCC():
    # Reset to known state
    disable_tdctcp()
    disable_dctcp()
    disable_tcp_ecn()
    if args.ecn:
        enable_tcp_ecn()
    if args.dctcp:
        enable_dctcp()
    if args.tdctcp:
        enable_tdctcp()

def resetCC():
    disable_dctcp()
    disable_tdctcp()
    disable_tcp_ecn()

def incast_iperf(net, topo):
    seconds = int(args.t)
    
    hosts = [net.get(c) for c in topo.HostList]
    h1 = hosts[0]
    h1.popen('iperf -s -i 1 > %s/iperf_h1.txt' % args.dir, shell=True)

    #waitListening(hosts[1], h1, 5001)

    monitors = []

    monitor = multiprocessing.Process(target=monitor_cpu, args=('%s/cpu.txt' % args.dir,))
    monitor.start()
    monitors.append(monitor)
    '''
    monitor = multiprocessing.Process(target=monitor_qlen, args=('s1-eth1', 0.01, '%s/qlen_s1-eth1.txt' % (args.dir)))
    monitor.start()
    monitors.append(monitor)

    monitor = multiprocessing.Process(target=monitor_devs_ng, args=('%s/txrate.txt' % args.dir, 0.01))
    monitor.start()
    monitors.append(monitor)
    '''
    Popen("rmmod tcp_probe; modprobe tcp_probe; cat /proc/net/tcpprobe > %s/tcp_probe.txt" % args.dir, shell=True)
    #CLI(net)

    for i in xrange(1, args.n):
        node_name = 'h%d' % (i+1)
        if args.udp:
            cmd = 'iperf -c ' + h1.IP() + '-t %d -i 1 -u -b %sM > %s/iperf_%s.txt' % (seconds, args.bw, args.dir, node_name)
        else:
            cmd = 'iperf -c ' + h1.IP() + ' -t %d -i 1 -Z cubic > %s/iperf_%s.txt' % (seconds, args.dir, node_name)
        hosts[i].sendCmd(cmd)

    if args.tcpdump:
	for i in xrange(args.n):
	    node_name = 'h%d' % (i+1)
	    hosts[i].popen('tcpdump -ni %s-eth0 -s0 -w \
		    %s/%s_tcpdump.pcap' % (node_name, args.dir, node_name), 
		    shell=True)
    progress(seconds+3)
    for monitor in monitors:
        monitor.terminate()

    h1.pexec("/bin/netstat -s > %s/netstat.txt" %
	    args.dir, shell=True)
    h1.pexec("/sbin/ifconfig > %s/ifconfig.txt" %
	    args.dir, shell=True)
    h1.pexec("/sbin/tc -s qdisc > %s/tc-stats.txt" %
    	    args.dir, shell=True)
    
    #net.stop()
    Popen("killall -9 cat ping top bwm-ng", shell=True).wait()

'''
Multi flows incast test
'''
import thread, threading
mutex = threading.Lock()
count=15
flow_num = { '2KB':10, '50KB':20, '1MB':8, '10MB':3, '25MB':0}
simDataPath = os.path.abspath(os.path.join('..', '..', 'data'))
def big_flow_first(tar, host, ofile):
    global count
    output = []
    change = 0
    _2KB = flow_num['2KB']
    _50KB = flow_num['50KB']
    _1MB = flow_num['1MB']
    _10MB = flow_num['10MB']
    _25MB = flow_num['25MB']
    while _2KB > 0 or _50KB > 0 or _1MB > 0 or _10MB > 0 or _25MB > 0:
        cmd = "curl -o /dev/null -w%%{time_connect}:%%{time_starttransfer}:%%{time_total} -s -d @%s/" % simDataPath
        suffix = ":"
        flag = False # Ensuring right data is input in case that error cmd is generated.
        if change == 0 and _25MB > 0:
            cmd += "25MB "
            _25MB -= 1
            suffix += "25MB"
            flag = True
        if change == 1 and _10MB > 0:
            cmd += "10MB "
            _10MB -= 1
            suffix += "10MB"
            flag = True
        if change == 2 and _1MB > 0:
            cmd += "1MB "
            _1MB -= 1
            suffix += "1MB"
            flag = True
        if change == 3 and _50KB > 0:
            cmd += "50KB "
            _50KB -= 1
            suffix += "50KB"
            flag = True
        if change == 4 and _2KB > 0:
            cmd += "2KB "
            _2KB -= 1
            suffix += "2KB"
            flag = True
        change = (change + 1) % 5
        if flag == False:
            continue
        cmd += tar
        print cmd
        r = host.cmd(cmd)
        #print r
        r += suffix
        output.append(r + "\n")
    if mutex.acquire():
        count -= 1
        f = open(ofile, "a")
        f.writelines(output)
        f.close()
        mutex.release()
             

def small_flow_first(tar, host, ofile):
    global count
    output = []
    change = 0
    _2KB = flow_num['2KB']
    _50KB = flow_num['50KB']
    _1MB = flow_num['1MB']
    _10MB = flow_num['10MB']
    _25MB = flow_num['25MB']
    while _2KB > 0 or _50KB > 0 or _1MB > 0 or _10MB > 0 or _25MB > 0:
        cmd = "curl -o /dev/null -w%%{time_connect}:%%{time_starttransfer}:%%{time_total} -s -d @%s/" % simDataPath
        suffix = ":"
        flag = False # Ensuring right data is input in case that error cmd is generated.
        if change == 4 and _25MB > 0:
            cmd += "25MB "
            _25MB -= 1
            suffix += "25MB"
            flag = True
        if change == 3 and _10MB > 0:
            cmd += "10MB "
            _10MB -= 1
            suffix += "10MB"
            flag = True
        if change == 2 and _1MB > 0:
            cmd += "1MB "
            _1MB -= 1
            suffix += "1MB"
            flag = True
        if change == 1 and _50KB > 0:
            cmd += "50KB "
            _50KB -= 1
            suffix += "50KB"
            flag = True
        if change == 0 and _2KB > 0:
            cmd += "2KB "
            _2KB -= 1
            suffix += "2KB"
            flag = True
        change = (change + 1) % 5
        if flag == False:
            continue
        cmd += tar
        print cmd
        r = host.cmd(cmd)
        #print r
        r += suffix
        output.append(r + "\n")
    if mutex.acquire():
        count -= 1
        f = open(ofile, "a")
        f.writelines(output)
        f.close()
        mutex.release()

def multi_flows_incast(net, topo):
    ofile = "%s/fct.txt" % args.dir

    # If fct.txt exists then delete the file
    if os.path.exists(ofile):
        os.remove(ofile)

    hosts = [net.get(c) for c in topo.HostList]
    httpServerAddr = os.path.abspath(os.path.join('..', '..', 'PostHTTPServer.py'))
    hosts[0].popen('python %s 80' % httpServerAddr, shell=True)
    for i in xrange(1, args.n, 2):
        thread.start_new_thread(big_flow_first, (hosts[0].IP(), hosts[i], ofile))
    for i in xrange(2, args.n, 2):
        thread.start_new_thread(small_flow_first, (hosts[0].IP(), hosts[i], ofile))
    while count > 0:
        continue
    print "saving to %s" % ofile

if __name__ == '__main__':
    setCC()

    lconfig = {'bw': args.bw, 
		   'max_queue_size': int(args.maxq),
		   'enable_ecn': args.ecn or args.dctcp or args.tdctcp,
	}
    topo = fattree4.Fattree(4,2)
    topo.createNodes()
    topo.createLinks(bw_c2a=args.bw, bw_a2e=args.bw, bw_e2h=args.bw,**lconfig)
    
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, switch=Switch,
	    controller=None, autoStaticArp=True, autoSetMacs=True)
    net.addController(
		'controller', controller=RemoteController,
		ip="127.0.0.1", port=6653)
    net.start()
    topo.set_ovs_protocol_13()
    # Set hosts IP addresses.
    fattree4.set_host_ip(net, topo)
    # Install proactive flow entries
    fattree4.install_proactive(net, topo)
    fattree4.pingTest(net)

    if args.fct:
        multi_flows_incast(net, topo)
    else:
        incast_iperf(net, topo)
    
    resetCC()