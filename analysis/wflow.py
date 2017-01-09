#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2016-2017 Martin Ueding <dev@martin-ueding.de>

from lxml import etree
import matplotlib.pyplot as pl
import numpy as np
import scipy.interpolate
import scipy.optimize

import util

def main(options):
    for xml_file in options.xml:
        convert_xml_to_tsv(xml_file)
        compute_t2_e(xml_file)

        t0 = find_root(xml_file + '.t2e.tsv')
        print('t0:', t0)

        compute_w(xml_file)

        w0 = find_root(xml_file + '.w.tsv')
        print('w0:', w0)

        visualize(xml_file, root=root)


def convert_xml_to_tsv(xml_file):
    tree = etree.parse(xml_file)

    results = tree.xpath('/WilsonFlow/wilson_flow_results')[0]
    wflow_step = results.xpath('wflow_step/text()')[0]
    wflow_gactij = results.xpath('wflow_gactij/text()')[0]

    t = np.fromstring(wflow_step, sep=' ')
    e = np.fromstring(wflow_gactij, sep=' ')
    e *= 8
    np.savetxt(xml_file + '.e.tsv', np.column_stack([t, e]))


def compute_t2_e(xml_file):
    t, e = util.load_columns(xml_file + '.e.tsv')
    np.savetxt(xml_file + '.t2e.tsv', np.column_stack([t, t**2 * e]))


def compute_w(xml_file):
    t, e = util.load_columns(xml_file + '.e.tsv')
    #w = t * np.gradient(t**2 * e, t)
    w = t * (2*t * e + t**2 * np.gradient(e, t))
    np.savetxt(xml_file + '.w.tsv', np.column_stack([t, w]))


def find_root(tsv_file, threshold=0.3):
    t, t2e = util.load_columns(tsv_file)
    x, y = interpolate_root(t, t2e - threshold)
    return (x, y + threshold)


def interpolate_root(x, y):
    f = scipy.interpolate.interp1d(x, y)
    root = scipy.optimize.brentq(f, np.min(x), np.min(x[y > 0]))
    return root, f(root)


def visualize(xml_file, root=None):
    t, t2e = util.load_columns(xml_file + '.t2e.tsv')

    fig = pl.figure(figsize=(16, 9))
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 4)

    ax1.plot(t, t2e)
    ax1.plot(t, np.ones(t.shape) * 0.3)

    if root is not None:
        x, y = root

        #ax2 = pl.axes([.65, .6, .3, .3], axisbg='0.9')
        ax2.plot(t, t2e, marker='o')
        ax2.plot(t, np.ones(t.shape) * 0.3)

        sel = t < 3 * x
        ax3.plot(t[sel], t2e[sel])
        ax3.plot(t[sel], np.ones(t[sel].shape) * 0.3)

        ax1.plot([x], [y], marker='o', alpha=0.3, color='red', markersize=20)
        ax2.plot([x], [y], marker='o', alpha=0.3, color='red', markersize=20)
        ax3.plot([x], [y], marker='o', alpha=0.3, color='red', markersize=20)

        ax2.set_xlim(0.7 * x, 1.3 * x)
        ax2.set_ylim(0.22, 0.38)

    #ax2.locator_params(nbins=6)
    #ax3.locator_params(nbins=6)

    ax1.set_title('All Computed Data')
    ax2.set_title('Interpolation')
    ax3.set_title('First $3 t_0$')

    for ax in [ax1, ax2, ax3]:
        ax.set_xlabel('Wilson Flow Time $t$')
        ax.set_ylabel(r'$t^2 \langle E \rangle$')

        util.dandify_axes(ax)

    util.dandify_figure(fig)

    fig.savefig(xml_file + '.t2e.pdf')
