#!/usr/bin/python3

# Usage: decode-solution.py <cnf-file> <sat-solver-output-file>

import argparse
import itertools
import re
import sys

def extract_coords(filename):
    # comments look like 'c var 1153 == ZERO at H(0,0)'
    prog = re.compile('c var (\\d+) == ([\\w\\s]+) at ([HV])\((\\d+),(\\d+)\)')
    mapping = {}
    forces = {}
    with open(filename) as f:
        for line in f:
            if line.startswith('p'): continue
            if not line.startswith('c'): return mapping, forces
            m = prog.match(line)
            if m is None: continue
            # m is of the form ('1153','ZERO','H','0','0')
            groups = m.groups()
            forces[int(groups[0])] = ("%s:%s(%s,%s)" % groups[1:])
            r, c = int(groups[3]), int(groups[4])
            coords = []
            for i, ch in enumerate(groups[1]):
                if groups[2] == 'H': coords.append((r,c+i,ch))
                elif groups[2] == 'V': coords.append((r+i,c,ch))
            mapping[int(groups[0])] = coords
    return mapping, forces

def strip_sat_solution(filename):
    pos = []
    with open(filename) as f:
        for line in f:
            if not line.startswith('v'): continue
            pos += [int(x) for x in line[1:].strip().split(' ') if int(x) > 0]
    return pos

def print_board(board):
    for row in board:
        for col in row:
            sys.stdout.write(col)
        sys.stdout.write("\n")

def print_relative_intersections(solution, coords):
    pos = [coords[val] for val in solution if coords.get(val) is not None]
    pcoord = dict([(''.join(map(lambda x: x[-1], item)),
                    set((x,y) for x,y,z in item)) for item in pos])
    begin = dict([(''.join(map(lambda x: x[-1], i)), (i[0][0],i[0][1])) \
                  for i in pos])
    for x,y in itertools.combinations(pcoord.keys(), 2):
        isect = pcoord[x] & pcoord[y]
        if len(isect) == 0: continue
        if len(isect) > 1: raise ValueError('Bad intersection: %s' % str(isect))
        isect = [x for x in isect][0]
        bx, by = begin[x], begin[y]
        xi = (isect[0] - bx[0]) + (isect[1] - bx[1])
        yi = (isect[0] - by[0]) + (isect[1] - by[1])
        print("{}:{}:{}:{}".format(x,xi,y,yi))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Decode a SAT solver solution for a wordcross')
    parser.add_argument('cnf_filename', type=str, help='input DIMACS file')
    parser.add_argument('solution_filename', type=str,
                        help='output of SAT solver')
    parser.add_argument('rows', type=int, help='number of rows')
    parser.add_argument('cols', type=int, help='number of columns')
    parser.add_argument('--format', choices=['ascii','forces','relative'],
                        default='ascii',)
    args = parser.parse_args()

    coords, raw_forces = extract_coords(args.cnf_filename)
    solution = strip_sat_solution(args.solution_filename)
    board = [[' ' for i in range(args.cols)] for i in range(args.rows)]
    forces = []
    for val in solution:
        if raw_forces.get(val) is not None:
            forces.append(raw_forces[val])
        if coords.get(val) is not None:
            for (r,c,ch) in coords[val]:
                board[r][c] = ch
    if args.format == 'ascii':
        print_board(board)
    elif args.format == 'forces':
        for force in forces: print(force)
    else:  # format == 'relative'
        print_relative_intersections(solution, coords)
