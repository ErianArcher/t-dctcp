import argparse
import re
import os
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('-f', dest="files", required=True)
parser.add_argument('-o', '--out', dest="out", default=None)
parser.add_argument('-B', '--bar', dest="bar",
                    help="Plot bar diagram of different bw",
                    action="store_true",
                    default=False)

args = parser.parse_args()
iperf_re = r'iperf_h\d+(\.txt)$'
def parse_file(f):
    last_line = ''
    for l in open(f).xreadlines():
        if len(l.strip()) != 0:
            last_line = l.strip()
    fields = last_line.split(' ')
    bw = float(fields[-2])
    return bw

def get_bws(dir):
    files = [f for f in os.listdir(dir) if re.match(iperf_re, f)]
    bws = []
    for f in files:
        bws.append(parse_file(os.path.join(dir,f)))
    return bws

def get_bws_server(f):
    bws = []
    for l in open(f).xreadlines():
        fields = re.split(r'\s+', l)
        if len(fields) == 9:
            secs = fields[2].split('-')
            if float(secs[1]) - float(secs[0]) > 2.:
                bws.append(float(fields[-3]))
    return bws

def output_bw():
    bws = get_bws_server(args.files)
    sum = 0.0
    for bw in bws:
        sum += bw
    output = os.path.join(args.files, r'throughput.txt')
    if args.out:
        output = os.path.join(args.out, r'throughput.txt')
    f = open(output, 'w+')
    f.write('The throughput of %s is %f' % (args.files, sum))
    print sum

def plot_bar():
    dir_name = []
    tps = []
    dirs = [d for d in os.listdir(args.files) if os.path.isdir(d)]
    dirs.sort()
    for d in dirs:
        flist = [os.path.join(d,f) for f in os.listdir(d) if re.match(r'^(throughput)\w*(\.txt)$', f)]
        if flist.count == 0:
            continue
        for l in open(flist[-1]).xreadlines():
            dir_name.append(d)
            tps.append(float(l.strip().split(' ')[-1]))
    plt.bar(dir_name, tps, color='rgb')
    if args.out:
        print 'saving to ', args.out
        plt.savefig(os.path.join(args.out, 'compare_tp.png'))
    else:
        plt.show()

if __name__=='__main__':
    if args.bar:
        plot_bar()
    else:
        output_bw()