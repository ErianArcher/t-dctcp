#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
from os import path

def gen_f(dir, size, metric=1024):
    length = size * metric
    if metric == 1024:
        fname = '%sKB' % size
    elif metric == 1024**2:
        fname = '%sMB' % size
    f = open(os.path.join(dir, fname), "w")
    for i in range(length):
        f.write('1')
    f.close()

if __name__=='__main__':
    dir = os.path.join('.', 'data')
    if not os.path.exists(dir):
        os.mkdir(dir)
    gen_f(dir, 2)
    gen_f(dir, 50)
    gen_f(dir, 1, 1024**2)
    gen_f(dir, 10, 1024**2)
    gen_f(dir, 25, 1024**2)
