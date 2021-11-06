#!/usr/bin/python3

# Usage: $ generate-sat.py wordfile rows cols
#
# Generates a DIMACS CNF file that's satisfiable iff there's a rows x cols
# puzzle containing all words in wordfile. wordfile should be a
# newline-separated list of words.

import argparse
import itertools
import re
import sys
import tempfile
from collections import defaultdict

# Global variable counter.
vc = 0
def new_var(): global vc; vc += 1; return vc
def num_vars(): global vc; return vc

def ensure_vars(nv): global vc; vc = nv

# Global clause counter.
cc = 0
def write_clause(f, c):
    global cc
    f.write((" ".join(["{}"] * len(c)) + " 0\n").format(*c))
    cc += 1
def num_clauses(): global cc; return cc

# Global comment accumulator.
comments = []
def add_comment(c):
    global comments
    comments.append(c)

def all_comments():
    global comments
    for c in comments: yield c

# Makes v true iff disjunction of vars in d is true
def disjunction_witness(cf, d, v=None):
    if v is None:
        v = new_var()
    write_clause(cf, [dv for dv in d] + [-v])
    for dv in d:
        write_clause(cf, [v, -dv])
    return v

# Makes v true iff conjunction of vars in c is true
def conjunction_witness(cf, c, v=None):
    if v is None:
        v = new_var()
    write_clause(cf, [-cv for cv in c] + [v])
    for cv in c:
        write_clause(cf, [-v, cv])
    return v

# Generates clauses satisfiable iff exactly one of the variables in vs is true.
def exactly_one_true(vs):
    vvs = tuple(v for v in vs)
    return [vvs] + [(-x,-y) for x,y in itertools.combinations(vvs, 2)]

# Generates clauses satisfiable iff at most one of the variables in vs is true.
def at_most_one_true(vs):
    vvs = tuple(v for v in vs)
    return [(-x,-y) for x,y in itertools.combinations(vvs, 2)]

# Generates clauses satisfiable iff at most one of the variables in vs is false.
def at_most_one_false(vs):
    vvs = tuple(v for v in vs)
    return [(x,y) for x,y in itertools.combinations(vvs, 2)]

# Given variables a, b, minout, and maxout, generates clauses that are
# satisfiable iff minout = min(a,b) and maxout = max(a,b).
def comparator(a, b, minout, maxout):
    return [(-maxout, a, b), (-a, maxout), (-b, maxout),
            (minout, -a, -b), (a, -minout), (b, -minout)]

def apply_comparator(cf, vin, i, j):
    newmin, newmax = new_var(), new_var()
    for clause in comparator(vin[i], vin[j], newmin, newmax):
        write_clause(cf, clause)
    #vin[i], vin[j] = newmin, newmax
    vin[i], vin[j] = newmax, newmin

def pairwise_sorting_network(cf, vin, begin, end):
    n, a = end - begin, 1
    while a < n:
        b, c = a, 0
        while b < n:
            apply_comparator(cf, vin, begin+b-a, begin+b)
            b, c = b+1, (c+1) % a
            if c == 0: b += a
        a *= 2

    a //= 4
    e = 1
    while a > 0:
        d = e
        while d > 0:
            b = (d+1) * a
            c = 0
            while b < n:
                apply_comparator(cf, vin, begin+b-d*a, begin+b)
                b, c = b+1, (c+1) % a
                if c == 0: b += a
            d //= 2
        a //= 2
        e = e*2 + 1

# Filter [vin[i], vin[i+n]) with [vin[j], vin[j+n)
def filter_network(cf, vin, i, j, n):
    for x in range(n):
        apply_comparator(cf, vin, i+x, j+n-1-x)

# Assert that exactly n of the vars in vin are true.
def exactly_n_true(cf, vin, n):
    n_true(cf, vin, n, True, True)

def at_most_n_true(cf, vin, n):
    n_true(cf, vin, n, True, False)

def at_least_n_true(cf, vin, n):
    n_true(cf, vin, n, False, True)

def n_true(cf, vin, n, at_most_n_true, at_least_n_true):
    if n == 0:
        if at_least_n_true: return
        for v in vin:
            write_clause(cf, (-v,))
        return
    n = n+1  # We'll select the top n+1, verify exactly one true.
    batches = len(vin) // n
    for b in range(1, batches):
        pairwise_sorting_network(cf, vin, 0, n)
        pairwise_sorting_network(cf, vin, b*n, (b+1)*n)
        filter_network(cf, vin, 0, b*n, n)
    # Now take care of the remainder, if there is one.
    rem = len(vin) - batches * n
    if rem > 0:
        pairwise_sorting_network(cf, vin, 0, n)
        pairwise_sorting_network(cf, vin, batches*n, len(vin))
        filter_network(cf, vin, n-rem, batches*n, rem)
    if at_least_n_true:
        # Assert that at most 1 of the first n are false
        for clause in at_most_one_false(vin[:n]):
            write_clause(cf, clause)
    if at_most_n_true:
        # Assert that at least 1 of the first n are false
        write_clause(cf, [-v for v in vin[:n]])

def generate_word_placements(cf, words, forces, relforces, args):
    rows, cols = args.rows, args.cols
    alphabet = set(ch for w in words for ch in w)
    pos = {}  # pos[(ch,row,col)] == "(row,col) is ch"
    for row in range(rows):
        for col in range(cols):
            vs = []
            for ch in alphabet:
                v = new_var()
                vs.append(v)
                pos[(ch,row,col)] = v
                #add_comment('var {} == ({},{}) = {}'.format(v,row,col,ch))
            # Every (row,col) can have at most one letter assigned.
            for clause in at_most_one_true(vs):
                write_clause(cf, clause)

    # Each (row,col) also has three vars associated with it:
    # * hvar: true iff some word is written horizontally on that square
    # * vvar: true iff some word is written vertically on that square
    # * stop: true iff the square is a left/right top/bottom boundary of a word
    hvar, vvar, stop = {}, {}, {}
    for row in range(rows):
        for col in range(cols):
            hvar[(row,col)] = new_var()
            vvar[(row,col)] = new_var()
            stop[(row,col)] = new_var()

    # A stop and an hvar can't cooccur.
    # A stop and a vvar can't cooccur.
    for row in range(rows):
        for col in range(cols):
            write_clause(cf, [-hvar[(row,col)], -stop[(row,col)]])
            write_clause(cf, [-vvar[(row,col)], -stop[(row,col)]])

    # Two hvars can't be vertically adjacent (unless they're also vvars).
    for r in range(rows-1):
        for c in range(cols):
            write_clause(cf, [-hvar[(r,c)], -hvar[(r+1,c)], vvar[(r,c)]])
            write_clause(cf, [-hvar[(r,c)], -hvar[(r+1,c)], vvar[(r+1,c)]])

    # Two vvars can't be horizontally adjacent (unless they're also hvars).
    for r in range(rows):
        for c in range(cols-1):
            write_clause(cf, [-vvar[(r,c)], -vvar[(r,c+1)], hvar[(r,c)]])
            write_clause(cf, [-vvar[(r,c)], -vvar[(r,c+1)], hvar[(r,c+1)]])

    # Finally, use pos, hvar, vvar, and stop to express word placements.
    hvar_witness = defaultdict(set)
    vvar_witness = defaultdict(set)
    pos_witness = defaultdict(set)
    stop_witness = defaultdict(set)
    placement_vars = defaultdict(dict)
    used = {}
    for wi, word in enumerate(words):
        vs = []
        # Horizontal placements
        for r in range(rows):
            for c in range(cols-len(word)+1):
                v = new_var()
                add_comment('var {} == {} at H({},{})'.format(v,word,r,c))
                if c > 0:
                    write_clause(cf, [-v, stop[(r,c-1)]])
                    stop_witness[stop[(r,c-1)]].add(v)
                vvars = []
                for i, ch in enumerate(word):
                    write_clause(cf, [-v, pos[(ch,r,c+i)]])
                    pos_witness[pos[(ch,r,c+i)]].add(v)
                    write_clause(cf, [-v, hvar[(r,c+i)]])
                    vvars.append(vvar[(r,c+i)])
                    hvar_witness[hvar[(r,c+i)]].add(v)
                if c+len(word) < cols:
                    write_clause(cf, [-v, stop[(r,c+len(word))]])
                    stop_witness[stop[(r,c+len(word))]].add(v)
                placement_vars[word][('H',r,c)] = v
                vs.append(v)
        # Symmetry-breaking: omit vertical placement of first word only.
        if rows != cols or wi != 0:
            # Vertical placements
            for r in range(rows-len(word)+1):
                for c in range(cols):
                    v = new_var()
                    add_comment('var {} == {} at V({},{})'.format(v,word,r,c))
                    if r > 0:
                        write_clause(cf, [-v, stop[(r-1,c)]])
                        stop_witness[stop[(r-1,c)]].add(v)
                    hvars = []
                    for i, ch in enumerate(word):
                        write_clause(cf, [-v, pos[(ch,r+i,c)]])
                        pos_witness[pos[(ch,r+i,c)]].add(v)
                        write_clause(cf, [-v, vvar[(r+i,c)]])
                        hvars.append(hvar[(r+i,c)])
                        vvar_witness[vvar[(r+i,c)]].add(v)
                    if r+len(word) < rows:
                        write_clause(cf, [-v, stop[(r+len(word),c)]])
                        stop_witness[stop[(r+len(word),c)]].add(v)
                    placement_vars[word][('V',r,c)] = v
                    vs.append(v)

        # Each word should be used at most once.
        for clause in at_most_one_true(vs):
            write_clause(cf, clause)
        used[word] = disjunction_witness(cf, vs)

    if args.lowerbound is None:
        for v in used.values(): write_clause(cf, [v])
    else:
        at_least_n_true(cf, list(used.values()), args.lowerbound)

    # Generate intersection vars: vars that are true iff a pair of words
    # intersect, based on placement vars.
    def word_intersection(w1, pos1, w2, pos2):
        if pos1[0] == 'V': w1, pos1, w2, pos2 = w2, pos2, w1, pos1
        if not (pos1[0] == 'H' and pos2[0] == 'V'): return None
        # pos1[0] == 'H' and pos2[0] == 'V' now
        if not (pos1[2] <= pos2[2] <= pos1[2] + len(w1) - 1): return None
        if not (pos2[1] <= pos1[1] <= pos2[1] + len(w2) - 1): return None
        if not (0 <= pos2[2]-pos1[2] < len(w1)): return None
        if not (0 <= pos1[1]-pos2[1] < len(w2)): return None
        if w1[pos2[2]-pos1[2]] != w2[pos1[1]-pos2[1]]: return None
        return (pos1[1], pos2[2])

    def word_pair(w1, w2): return (w1, w2) if w1 < w2 else (w2, w1)
    def word_pairs(ws):
        for w1, w2 in itertools.combinations(ws, 2):
            yield word_pair(w1, w2)
    count = 0
    # Maps pair of (w1, w2) to list of vars that are true iff they intersect.
    disjunctions = defaultdict(list)
    for w1, w2 in word_pairs(words):
        for pos1, v1 in placement_vars[w1].items():
            for pos2, v2 in placement_vars[w2].items():
                wi = word_intersection(w1, pos1, w2, pos2)
                if wi is None: continue
                #print("%s + %s at %s (%s, %s)" % \
                #      (w1, w2, str(wi), str(pos1), str(pos2)))
                count += 1
                disjunctions[(w1,w2)].append(conjunction_witness(cf, [v1,v2]))
    #print("%s possible intersection pairs" % count)

    # maps (w1,w2) to a var that's true iff they intersect
    intersects = {}
    for wp, dis in disjunctions.items():
        intersects[wp] = disjunction_witness(cf, dis)

    # Define level-0 reachability vars (intersections)
    reachable = [{} for i in range(len(words)-1)]
    for wp in word_pairs(words):
        if intersects.get(wp) is None:
            v = new_var()
            reachable[0][wp] = v
            write_clause(cf, [-v])
        else:
            reachable[0][wp] = intersects[wp]

    # Define level i reachability in terms of level (i-1)
    for i in range(1,len(reachable)):
        for w1, w2 in word_pairs(words):
            dis = []
            for w in words:
                if w == w1 or w == w2: continue
                wa, wb = word_pair(w1,w), word_pair(w,w2)
                if intersects.get(wa) is None: continue
                conj = [intersects[wa], reachable[i-1][wb]]
                dis.append(conjunction_witness(cf, conj))
            if len(dis) == 0:
                v = new_var()
                reachable[i][(w1,w2)] = v
                write_clause(cf, [-v])
            else:
                reachable[i][(w1,w2)] = disjunction_witness(cf, dis)

    # w1 is reachable from w2 if it's i-reachable for some i
    # Assert that everything is (len(words)-1) reachable from everything
    for w1, w2 in word_pairs(words):
        dis = [reachable[i][(w1,w2)] for i in range(len(reachable))]
        both_used = conjunction_witness(cf, [used[w1], used[w2]])
        write_clause(cf, [-both_used, disjunction_witness(cf, dis)])

    if args.empty is not None:
        empty = {}
        for r in range(rows):
            for c in range(cols):
                ec = [-hvar[(r,c)], -vvar[(r,c)]]
                empty[(r,c)] = conjunction_witness(cf, ec)

        # At most args.empty positions are empty.
        at_most_n_true(cf, list(empty.values()), args.empty)

    # Don't let an hvar or vvar get set unless there's a placement var that
    # can serve as a witness for it. Otherwise, the solver will choose a
    # packing that's too tight by setting hvars/vvars where there aren't
    # any words.
    for hw, ws in hvar_witness.items():
        write_clause(cf, [-hw] + list(ws))
    for vw, ws in vvar_witness.items():
        write_clause(cf, [-vw] + list(ws))
    if args.extra:
        for sw, ws in stop_witness.items():
            write_clause(cf, [-sw] + list(ws))
        for pw, ws in pos_witness.items():
            write_clause(cf, [-pw] + list(ws))

    # Handle any forces
    for word, pos in forces.items():
        clause = []
        for rj in range(-args.jitter,args.jitter+1):
            for cj in range(-args.jitter,args.jitter+1):
                npos = (pos[0], pos[1]+rj, pos[2]+cj)
                if placement_vars[word].get(npos) is not None:
                    clause.append(placement_vars[word][npos])
        write_clause(cf, clause)

    # Handle any relative forces
    def reloffset(x,p1,p2):
        o, r, c = x
        if o == 'H':
            return ('V',r-p2,c+p1)
        else: # o == 'V'
            return ('H',r+p1,c-p2)

    for w1, p1, w2, p2 in relforces:
        for x1, v1 in placement_vars[w1].items():
            x2 = reloffset(x1,p1,p2)
            v2 = placement_vars[w2].get(x2)
            if v2 is not None:
                add_comment('force: {} at {} <=> {} at {}'.format(w1,x1,w2,x2))
                write_clause(cf, [-v1, v2])
                write_clause(cf, [-v2, v1])
            else:
                add_comment('force: {} can''t be at {}'.format(w1,x1))
                write_clause(cf, [-v1])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Encode a wordcross problem as SAT")
    parser.add_argument('wordfile', type=str, help='input words, one per line')
    parser.add_argument('rows', type=int, help='number of rows')
    parser.add_argument('cols', type=int, help='number of columns')
    parser.add_argument('--extra',
                        action='store_true',
                        help='add some unnecessary clauses that may help')
    parser.add_argument('--forcefile',
                        help='file containing forced placements')
    parser.add_argument('--jitter', type=int, default=0,
                        help='jitter to apply to forced placements')
    parser.add_argument('--relforcefile',
                        help='file containing relative forces')
    parser.add_argument('--lowerbound', type=int,
                        help='at least this many words must be placed ' + \
                        '(default: all)')
    parser.add_argument('--empty', type=int,
                        help='force at most this many empty cells')

    args = parser.parse_args()

    words = [w.strip() for w in open(args.wordfile) if len(w.strip()) > 0]

    forces = {}
    if args.forcefile is not None:
        prog = re.compile('([HV])\((\\d+),(\\d+)\)')
        for line in open(args.forcefile):
            if line.startswith('//') or line.strip() == '': continue
            word, pos = line.strip().split(':')
            m = prog.match(pos)
            if m is None: raise Exception("Invalid forcefile line: " + line)
            forces[word] = (
                m.groups()[0], int(m.groups()[1]), int(m.groups()[2]))

    relforces = []
    if args.relforcefile is not None:
        for line in open(args.relforcefile):
            if line.startswith('//') or line.strip() == '': continue
            w1, p1, w2, p2 = line.strip().split(':')
            relforces.append((w1,int(p1),w2,int(p2)))

    with tempfile.TemporaryFile(mode='w+t') as cf:
        generate_word_placements(cf, words, forces, relforces, args)

        for comment in all_comments():
            sys.stdout.write('c {}\n'.format(comment))
        sys.stdout.write('p cnf {0} {1}\n'.format(num_vars(), num_clauses()))
        cf.seek(0)
        for line in cf:
            sys.stdout.write(line)
        sys.stdout.write('\n')
