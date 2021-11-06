#!/usr/bin/python3

# Usage: block-solution.py <cnf-file> <sat-solver-output-file>
#
# Finds a clause that blocks the solution in the solver output.

import re
import sys

def extract_vars(filename):
    # comments look like 'c var 1153 == ZERO at H(0,0)'
    prog = re.compile('c var (\\d+) == \\w+ at [HV]\(\\d+,\\d+\)')
    vs = set()
    with open(filename) as f:
        for line in f:
            if line.startswith('p'): continue
            if not line.startswith('c'): return vs
            m = prog.match(line)
            if m is None: continue
            vs.add(m.groups()[0])
    return vs

def strip_sat_solution(filename):
    pos = set()
    with open(filename) as f:
        for line in f:
            if not line.startswith('v'): continue
            for x in line[1:].strip().split(' '):
                if int(x) > 0:
                    pos.add(x)
    return pos

def print_board(board):
    for row in board:
        for col in row:
            sys.stdout.write(col)
        sys.stdout.write("\n")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: %s <cnf-file> <solver-output-file>' % sys.argv[0])
        sys.exit(1)
    cnf_file, solver_output_file = sys.argv[1:]
    vs = extract_vars(cnf_file)
    solution = strip_sat_solution(solver_output_file)
    print(' '.join([str(-int(x)) for x in vs & solution]) + ' 0')
