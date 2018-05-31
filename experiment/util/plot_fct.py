import argparse
import os
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('-f', dest="files", nargs='+', required=True)
parser.add_argument('-o', '--out', dest="out", default=None)

args = parser.parse_args()

def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        plt.text(rect.get_x()+rect.get_width()/2.-0.2, 1.03*height, '%s' % int(height))

def parse_file(f):
    fct = []
    for l in open(f).xreadlines():
        fields = l.split(':')
        if len(fields) == 4:
            time = (float(fields[2]) - float(fields[1])) * 1000.
            if time < 5000.:
                fct.append(time)
    return fct

def parse_file_flows(f):
    fct = {'2KB':[], '50KB':[], '1MB':[], '10MB':[], '25MB':[]}
    for l in open(f).xreadlines():
        fields = l.split(':')
        if len(fields) == 4:
            time = (float(fields[2]) - float(fields[1])) * 1000.
            fct[fields[-1].strip()].append(time)
    return fct


def generate_cdf():
    plt.title("Flow Completion Time Comparison", fontsize=16)
    for f in args.files:
        name = os.path.split(os.path.split(f)[0])[-1].split('-')[0]
        if name == 'tdctcp':
            name = 't-dctcp'
        fct = parse_file(f)
        x = np.sort(fct)
        y = 1. * np.arange(len(fct)) / (len(fct) - 1)
        plt.plot(x, y, label=name.upper())
    plt.legend(fontsize=14)
    plt.margins(0.02)
    plt.xlabel("Complete Time (ms)", fontsize=14)
    plt.ylabel("Percentile", fontsize=14)
    if args.out:
        plt.savefig(os.path.join(args.out,'fct_cdf.png'))
        plt.clf()
    else:
        plt.show()

def generate_avg_bar():
    plt.title("Flow Average Completion Time Comparison", fontsize=16)
    width = 0.8
    bar_width = width / len(args.files)
    flow_sizes = ['2KB', '50KB', '1MB', '10MB']
    index = list(range(len(flow_sizes)))
    for f in args.files:
        name = os.path.split(os.path.split(f)[0])[-1].split('-')[0]
        fct = parse_file_flows(f)
        if name == 'tdctcp':
            name = 't-dctcp'
        fct_avg = []
        for i in xrange(len(flow_sizes)):
            v = fct[flow_sizes[i]]
            if len(v) > 0:
                fct_avg.append(reduce(lambda x, y: x+y, v)/len(v))
            else:
                fct_avg.append(0.)
        a = plt.bar(index, fct_avg, tick_label=flow_sizes, width=bar_width, alpha=0.9, label=name.upper())
        autolabel(a)
        for i in range(len(flow_sizes)):
            index[i] += bar_width
    plt.legend(fontsize=14)
    plt.xlabel("Flow Size", fontsize=14)
    plt.ylabel("AVG Complete Time (ms)", fontsize=14)
    if args.out:
        plt.savefig(os.path.join(args.out,'fct_avg.png'))
        plt.clf()
    else:
        plt.show()

if __name__=='__main__':
    generate_cdf()
    
    generate_avg_bar()