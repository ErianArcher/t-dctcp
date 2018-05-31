from helper import *
from collections import defaultdict
import argparse
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', dest="port", default='5001')
parser.add_argument('-f', dest="files", nargs='+', required=True)
parser.add_argument('-o', '--out', dest="out", default=None)
parser.add_argument('-H', '--histogram', dest="histogram",
                    help="Plot histogram of sum(cwnd_i)",
                    action="store_true",
                    default=False)

args = parser.parse_args()

def first(lst):
    return map(lambda e: e[0], lst)

def second(lst):
    return map(lambda e: e[1], lst)

"""
Sample line:
2.221032535 10.0.0.2:39815 10.0.0.1:5001 32 0x1a2a710c 0x1a2a387c 11 2147483647 14592 85
"""
p2ip = dict()
def parse_file(f):
    global p2ip
    global srtt
    times = defaultdict(list)
    cwnd = defaultdict(list)
    for l in open(f).xreadlines():
        fields = l.strip().split(' ')
        if len(fields) != 11:
            break
        if fields[2].split(':')[1] != args.port:
            continue
        sport = int(fields[1].split(':')[1])
        if p2ip.get(sport) == None:
            p2ip[sport] = fields[1].split(':')[0]
        times[sport].append(float(fields[0]))

        c = int(fields[6])
        cwnd[sport].append(c * 1480 / 1024.0)
    return times, cwnd

def parse_file_rtt(f):
    srtt = []
    for l in open(f).xreadlines():
        fields = l.strip().split(' ')
        if len(fields) != 11:
            break
        if fields[2].split(':')[1] != args.port:
            srtt.append(int(fields[-1]))
    return srtt
        

added = defaultdict(int)
events = []

def plot_cwnds(ax):
    global events
    global p2ip
    for f in args.files:
        times, cwnds = parse_file(f)
        for port in sorted(cwnds.keys()):
            t = times[port]
            cwnd = cwnds[port]
            print '%d avg cwnd: %f' % (port, reduce(lambda x, y: x+y, cwnd)/len(cwnd))
            events += zip(t, [port]*len(t), cwnd)
            ax.plot(t, cwnd, label=p2ip[port])
    
    events.sort()

def plot_rtt(ax):
    for f in args.files:
        name = os.path.split(os.path.split(f)[0])[-1].split('-')[0]
        if name == 'tdctcp':
            name = 't-dctcp'
        srtt = parse_file_rtt(f)
        # plot CDF diagram
        srtt_ms = map(lambda x: x/1000, srtt)
        sorted_srtt = np.sort(srtt_ms)
        p = 1. * np.arange(len(srtt)) / (len(srtt) - 1)
        ax.plot(sorted_srtt, p, label=name.upper())

        rttf = open('%s/rtt.txt' % args.out, "w")
        srtt.sort()
        pack_count = len(srtt)
        avg = 0.0
        for i in xrange(pack_count):
            avg += srtt[i] / pack_count
        rttf.write('AVG: %lf\n' % avg)
        rttf.write('MAX: %d\n' % srtt[-1])
        rttf.write('99.9th: %d\n' % srtt[int(pack_count*0.999)])
        rttf.write('99th: %d\n' % srtt[int(pack_count*0.99)])
        rttf.write('75th: %d\n' % srtt[int(pack_count*0.75)])
        rttf.write('50th: %d\n' % srtt[int(pack_count*0.50)])
        rttf.write('25th: %d\n' % srtt[int(pack_count*0.25)])
        rttf.write('MIN: %d\n' % srtt[0])
        rttf.close()

total_cwnd = 0
cwnd_time = []

min_total_cwnd = 10**10
max_total_cwnd = 0
totalcwnds = []

m.rc('figure', figsize=(16, 6))
fig_cwnd = plt.figure()
plots = 1
if args.histogram:
    plots = 2

axPlot = fig_cwnd.add_subplot(1, plots, 1)
plot_cwnds(axPlot)

for (t,p,c) in events:
    if added[p]:
        total_cwnd -= added[p]
    total_cwnd += c
    cwnd_time.append((t, total_cwnd))
    added[p] = c
    totalcwnds.append(total_cwnd)

axPlot.plot(first(cwnd_time), second(cwnd_time), lw=2, label="$\sum_i W_i$")
axPlot.grid(True)
axPlot.legend()
axPlot.set_xlabel("seconds")
axPlot.set_ylabel("cwnd KB")
axPlot.set_title("TCP congestion window (cwnd) timeseries")

if args.histogram:
    axHist = fig_cwnd.add_subplot(1, 2, 2)
    n, bins, patches = axHist.hist(totalcwnds, 50, normed=1, facecolor='green', alpha=0.75)

    axHist.set_xlabel("bins (KB)")
    axHist.set_ylabel("Fraction")
    axHist.set_title("Histogram of sum(cwnd_i)")

if args.out:
    print 'saving to', args.out
    plt.savefig(args.out+'/cwnd.png')
else:
    plt.show()

fig_rtt = plt.figure()
axPlot = fig_rtt.add_subplot(1, 1, 1)
plot_rtt(axPlot)
axPlot.set_xlabel('RTT (ms)', fontsize=20)
axPlot.set_ylabel('Percentile', fontsize=20)
axPlot.set_title("CDF diagram of RTT -- %s" % args.out, fontsize=20)
plt.legend(fontsize=16)
plt.margins(0.02)
if args.out:
    print 'saving to', args.out
    plt.savefig(args.out+'/CDF_RTT.png')
else:
    plt.show()