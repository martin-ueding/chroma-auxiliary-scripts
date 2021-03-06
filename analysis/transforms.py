#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2016-2018 Martin Ueding <mu@martin-ueding.de>

import collections
import csv
import glob
import json
import os
import pprint

import numpy as np
import pandas as pd

import names
import util


PERCENTILE_LOW = 50 - 34.13
PERCENTILE_HIGH = 50 + 34.13


def chunks(l, n):
    '''
    Yield successive n-sized chunks from l.

    http://stackoverflow.com/a/312464
    '''
    for i in range(0, len(l), n):
        yield l[i:i + n]


def get_multiple_percentiles(datas):
    y = np.array([np.percentile(data, 50) for data in datas])
    yerr_down = y - np.array([np.percentile(data, PERCENTILE_LOW) for data in datas])
    yerr_up = np.array([np.percentile(data, PERCENTILE_HIGH) for data in datas]) - y
    return y, yerr_down, yerr_up


def get_percentiles(data):
    y = np.percentile(data, 50)
    yerr_down = y - np.percentile(data, PERCENTILE_LOW)
    yerr_up = np.percentile(data, PERCENTILE_HIGH) - y
    return y, yerr_down, yerr_up


def gflops_per_node_converter(solver_data, update_data):
    gflops_dist = np.array(solver_data['gflops'])
    nodes = update_data['nodes']
    return get_percentiles(gflops_dist / nodes)


def iteration_converter(solver_data, update_data):
    gflops_dist = solver_data['iters']
    return get_percentiles(gflops_dist)


def residual_converter(solver_data, update_data):
    gflops_dist = solver_data['residuals']
    return get_percentiles(gflops_dist)


#subgrid_volume = update_data['subgrid_volume']


def convert_solver_list(dirname, converter, outname):
    filename_in = os.path.join(dirname, 'extract', 'extract-log.json')

    if not os.path.isfile(filename_in):
        print('File is missing:', filename_in)
        return

    with open(filename_in) as f:
        data = json.load(f)

    results = collections.defaultdict(list)

    for update_no, update_data in sorted(data.items()):
        for solver, solver_data in update_data['solvers'].items():
            try:
                result = list(converter(solver_data, update_data))
            except KeyError as e:
                print(filename_in, e)
                continue

            results[solver].append([float(update_no)] + result)

    to_json = {}

    for solver, solver_results in results.items():
        if len(solver_results) > 0:
            np.savetxt(os.path.join(
                dirname, 'extract',
                'extract-solver-{}-{}.tsv'.format(util.make_safe_name(solver), outname)),
                solver_results)

            to_json[solver] = list(zip(*sorted(solver_results)))

    with open(names.json_extract(dirname, outname), 'w') as f:
        json.dump(to_json, f, indent=4, sort_keys=True)


def merge_json_shards(filenames, dest):
    merged = {}

    for filename in filenames:
        with open(filename) as f:
            data = json.load(f)

        for key, val in data.items():
            assert key not in merged, key
            merged[key] = val

    with open(dest, 'w') as f:
        json.dump(merged, f, indent=4, sort_keys=True)


def merge_dict_2(base, add):
    for key1, val1 in add.items():
        for key2, val2 in val1.items():
            base[key1][key2] += val2


def unique_rows(a):
    '''
    http://stackoverflow.com/a/31097277
    '''
    a = np.ascontiguousarray(a)
    unique_a = np.unique(a.view([('', a.dtype)]*a.shape[1]))
    return unique_a.view(a.dtype).reshape((unique_a.shape[0], a.shape[1]))


def merge_tsv_shards(shard_names, merged_name):
    all_data = [
        data
        for data in map(np.atleast_2d, map(np.loadtxt, shard_names))
        if data.shape[1] > 0]

    if len(all_data) == 0:
        merged = []
    else:
        merged = np.row_stack(all_data)
        merged = util.sort_by_first_column(merged)
        merged = unique_rows(merged)

    np.savetxt(merged_name, merged)


def prepare_solver_iters(dirname):
    with open(os.path.join(dirname, 'extract', 'extract-solver_iters.json')) as f:
        data = json.load(f)

    for solver, tuples in sorted(data.items()):
        x = sorted(map(float, tuples.keys()))
        datas = [gflops for subgrid_volume, gflops in sorted(tuples.items())]
        y, yerr_down, yerr_up = percentiles(datas)

        np.savetxt(os.path.join(dirname, 'extract', util.make_safe_name('extract-solver_iters-{}.tsv'.format(solver))),
                   np.column_stack([x, y, yerr_down, yerr_up]))


def convert_to_md_time(dirname, name_in):
    file_in = os.path.join(dirname, 'extract', 'extract-md_time.tsv')
    data = np.atleast_2d(np.loadtxt(file_in))

    if data.shape[1] == 0:
        return

    update_no = data[:, 0]
    md_time = data[:, 1]

    data = np.atleast_2d(np.loadtxt(os.path.join(dirname, 'extract-{}.tsv'.format(name_in))))
    update_no_2 = data[:, 0]
    y = data[:, 1]

    eq = update_no == update_no_2
    if (isinstance(eq, bool) and not eq) or (isinstance(eq, np.ndarray) and not all(eq)):
        assert False, "Update Numbers must match for {}.\n{}\n{}".format(name_in, str(update_no), str(update_no_2))

    np.savetxt(os.path.join(dirname, 'extract', 'extract-{}-vs-md_time.tsv'.format(name_in)),
               np.column_stack([md_time, y]))


def io_delta_h_to_exp(path_in, path_out):
    t, delta_h = util.load_columns(path_in, 2)
    exp = np.exp(- delta_h)
    np.savetxt(path_out, np.column_stack([t, exp]))


def io_time_to_minutes(path_in, path_out):
    update_no, seconds = util.load_columns(path_in, 2)
    np.savetxt(path_out, np.column_stack([update_no, seconds / 60]))


def convert_tau0_to_md_time(file_in, file_out):
    result = []
    try:
        update_no, tau0 = util.load_columns(file_in, 2)
    except ValueError as e:
        print(e)
    else:
        md_time = np.cumsum(tau0)
        assert tau0.shape == md_time.shape
        result = np.column_stack([update_no, md_time])
    np.savetxt(file_out, result)


def delta_delta_h(dirname):
    result = []

    try:
        update_no_ddh, ddh = util.load_columns(os.path.join(dirname,'extract',  'extract-DeltaDeltaH.tsv'), 2)
        update_no_dh, dh = util.load_columns(os.path.join(dirname,'extract',  'extract-deltaH.tsv'), 2)
    except ValueError:
        pass
    else:
        for i, update_no in enumerate(update_no_ddh):
            j = np.where(update_no == update_no_dh)[0][0]
            print(update_no, '->', j)
            result.append((update_no, ddh[i] / dh[j]))

    np.savetxt(os.path.join(dirname,'extract',  'extract-DeltaDeltaH_over_DeltaH.tsv'),
               result)


def io_running_mean(path_in, path_out, window=100):
    x = pd.read_table(path_in, header=None, squeeze=True, names=['y'], sep=' ')
    r = x.rolling(window)
    rolling_mean = r.mean().dropna()
    rolling_mean.to_csv(path_out, sep='\t')


def io_log_json_to_long(path_in, path_out):
    cols = ['gflops', 'iters', 'residuals']

    rows = []

    print(path_in)

    with open(path_in) as f:
        updates = json.load(f)

    for update, update_data in sorted(updates.items()):
        nodes = update_data['nodes']
        subgrid_volume = update_data['subgrid_volume']

        for solver, solver_data in update_data['solvers'].items():
            print(update, solver, solver_data.keys())
            for items in zip(*[solver_data[c] for c in cols if c in solver_data]):
                if len(items) == 3:
                    gflops, iters, residual = items
                else:
                    gflops, iters = items
                    residual = 'NA'

                rows.append([
                    update,
                    nodes,
                    subgrid_volume,
                    solver,
                    gflops,
                    iters,
                    residual
                ])

    with open(path_out, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['Update', 'Ranks', 'Subgrid_Volume', 'Solver', 'GFLOPS', 'Iterations', 'Residual'])
        for row in rows:
            writer.writerow(row)



if __name__ == '__main__':
    io_running_mean('/home/mu/Dokumente/Studium/Master_Science_Physik/Masterarbeit/Runs/0106-Mpi660-L16-T32/extract/extract-AcceptP.tsv', 'test.tsv')
